"""Tests for rebuild signaling.

Stage 2 step 5 makes the delete-in-place rebuild window visible to readers.
A preprocessing run marks its output directory with a ``.building`` sentinel
that survives any failure, and every search request is rejected before it can
reach a half-built pair: a live build is retryable ``index_rebuilding``, a
leftover sentinel with no build running is the non-retryable
``index_interrupted``.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import bgc_viewer.app as app_module
import bgc_viewer.preprocessing as preprocessing_module
from bgc_viewer.app import app
from bgc_viewer.search.build_state import (
    SENTINEL_NAME,
    IndexInterruptedError,
    IndexRebuildingError,
    building,
    clear_building,
    guard_build_state,
    is_building,
    mark_building,
    sentinel_path,
)
from bgc_viewer.search.api import error_response

LEVELS = ("protocluster", "region", "record")


def _never_live() -> bool:
    return False


def _always_live() -> bool:
    return True


class TestSentinelPrimitives:
    def test_mark_creates_the_named_sentinel(self, temp_dir):
        path = mark_building(temp_dir)
        assert path == temp_dir / SENTINEL_NAME
        assert is_building(temp_dir)

    def test_sentinel_records_a_start_time_for_diagnostics(self, temp_dir):
        mark_building(temp_dir)
        started = sentinel_path(temp_dir).read_text(encoding="utf-8")
        assert datetime.fromisoformat(started)

    def test_clear_removes_it_and_is_idempotent(self, temp_dir):
        mark_building(temp_dir)
        clear_building(temp_dir)
        assert not is_building(temp_dir)
        clear_building(temp_dir)
        assert not is_building(temp_dir)

    def test_mark_creates_a_missing_output_directory(self, temp_dir):
        target = temp_dir / "nested" / "out"
        mark_building(target)
        assert is_building(target)


class TestBuildingContextManager:
    def test_sentinel_wraps_the_block(self, temp_dir):
        assert not is_building(temp_dir)
        with building(temp_dir) as path:
            assert path == sentinel_path(temp_dir)
            assert is_building(temp_dir)
        assert not is_building(temp_dir)

    def test_failure_leaves_the_sentinel_behind(self, temp_dir):
        with pytest.raises(RuntimeError, match="boom"):
            with building(temp_dir):
                raise RuntimeError("boom")
        assert is_building(temp_dir)

    def test_base_exception_leaves_the_sentinel_behind(self, temp_dir):
        with pytest.raises(KeyboardInterrupt):
            with building(temp_dir):
                raise KeyboardInterrupt
        assert is_building(temp_dir)

    def test_a_recovered_run_clears_a_marker_left_by_a_failed_one(self, temp_dir):
        with pytest.raises(RuntimeError):
            with building(temp_dir):
                raise RuntimeError("first run died")
        assert is_building(temp_dir)
        with building(temp_dir):
            pass
        assert not is_building(temp_dir)


class TestGuardBuildState:
    def test_quiet_directory_passes(self, temp_dir):
        assert guard_build_state(temp_dir, build_is_live=_never_live) is None

    def test_live_build_is_retryable_rebuilding_without_a_sentinel(self, temp_dir):
        # The run was accepted but its worker thread has not written the
        # sentinel yet; the in-process flag still has to reject the request.
        with pytest.raises(IndexRebuildingError):
            guard_build_state(temp_dir, build_is_live=_always_live)

    def test_stale_sentinel_without_a_build_is_interrupted(self, temp_dir):
        mark_building(temp_dir)
        with pytest.raises(IndexInterruptedError) as excinfo:
            guard_build_state(temp_dir, build_is_live=_never_live)
        assert SENTINEL_NAME in str(excinfo.value)

    def test_live_build_wins_over_a_stale_sentinel(self, temp_dir):
        mark_building(temp_dir)
        with pytest.raises(IndexRebuildingError):
            guard_build_state(temp_dir, build_is_live=_always_live)

    def test_codes_are_distinct(self):
        assert IndexRebuildingError().code == "index_rebuilding"
        assert IndexInterruptedError().code == "index_interrupted"

    def test_both_map_to_conflict(self):
        assert error_response(IndexRebuildingError())[1] == 409
        assert error_response(IndexInterruptedError("/tmp/out"))[1] == 409

    def test_error_envelope_carries_code_and_message(self):
        payload, status = error_response(IndexInterruptedError("/tmp/out"))
        assert status == 409
        assert payload["error"]["code"] == "index_interrupted"
        assert "Rerun preprocessing" in payload["error"]["message"]


class TestPreprocessingSentinel:
    def test_sentinel_exists_before_the_database_is_deleted(
        self, monkeypatch, temp_dir, sample_json_file
    ):
        seen = {}
        real = preprocessing_module.create_attributes_database

        def spy(path):
            seen["building"] = is_building(path.parent)
            return real(path)

        monkeypatch.setattr(preprocessing_module, "create_attributes_database", spy)
        preprocessing_module.preprocess_antismash_files(
            str(temp_dir), str(temp_dir / "attributes.db")
        )
        assert seen["building"] is True

    def test_successful_run_leaves_no_sentinel(self, temp_dir, sample_json_file):
        preprocessing_module.preprocess_antismash_files(
            str(temp_dir), str(temp_dir / "attributes.db")
        )
        assert not is_building(temp_dir)

    def test_failed_index_build_keeps_the_sentinel(
        self, monkeypatch, temp_dir, sample_json_file
    ):
        def explode(*args, **kwargs):
            raise RuntimeError("index build failed")

        monkeypatch.setattr(preprocessing_module, "build_index", explode)
        with pytest.raises(RuntimeError, match="index build failed"):
            preprocessing_module.preprocess_antismash_files(
                str(temp_dir), str(temp_dir / "attributes.db")
            )
        assert is_building(temp_dir)
        assert not (temp_dir / "tantivy.index").exists()

    def test_rerunning_over_a_stale_sentinel_clears_it(
        self, temp_dir, sample_json_file
    ):
        mark_building(temp_dir)
        preprocessing_module.preprocess_antismash_files(
            str(temp_dir), str(temp_dir / "attributes.db")
        )
        assert not is_building(temp_dir)

    def test_sentinel_is_not_picked_up_as_a_source_file(
        self, temp_dir, sample_json_file
    ):
        mark_building(temp_dir)
        result = preprocessing_module.preprocess_antismash_files(
            str(temp_dir), str(temp_dir / "attributes.db")
        )
        assert result["files_processed"] == 1


@pytest.fixture
def search_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _select_database(client, db_path) -> None:
    with client.session_transaction() as sess:
        sess["current_database_path"] = str(db_path)


def _search(client, level: str):
    return client.post(f"/api/search/{level}", json={"query": "pfam:PF00501"})


class TestSearchEndpointsDuringRebuild:
    def test_live_build_rejects_every_level_as_rebuilding(
        self, monkeypatch, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        # A usable index exists, so the 409 can only come from the guard.
        assert (db_path.parent / "tantivy.index").exists()
        monkeypatch.setitem(app_module.PREPROCESSING_STATUS, "is_running", True)
        for level in LEVELS:
            response = _search(search_client, level)
            assert response.status_code == 409, level
            assert json.loads(response.data)["error"]["code"] == "index_rebuilding"

    def test_stale_sentinel_rejects_every_level_as_interrupted(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        mark_building(db_path.parent)
        assert not app_module.PREPROCESSING_STATUS["is_running"]
        for level in LEVELS:
            response = _search(search_client, level)
            assert response.status_code == 409, level
            assert json.loads(response.data)["error"]["code"] == "index_interrupted"

    def test_a_read_request_does_not_clear_a_stale_sentinel(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        mark_building(db_path.parent)
        _search(search_client, "protocluster")
        assert is_building(db_path.parent)

    def test_request_body_is_still_validated_before_the_guard(
        self, monkeypatch, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        monkeypatch.setitem(app_module.PREPROCESSING_STATUS, "is_running", True)
        response = search_client.post("/api/search/protocluster", json={"query": 123})
        assert response.status_code == 400
        assert json.loads(response.data)["error"]["code"] == "invalid_request"

    def test_no_sentinel_and_no_build_serves_normally(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = _search(search_client, "protocluster")
        assert response.status_code == 200
        assert len(json.loads(response.data)["hits"]) == 2

    def test_missing_index_still_wins_when_nothing_is_building(
        self, search_client, temp_dir
    ):
        empty_db = temp_dir / "attributes.db"
        empty_db.write_text("")
        _select_database(search_client, empty_db)
        response = _search(search_client, "protocluster")
        assert response.status_code == 404
        assert json.loads(response.data)["error"]["code"] == "missing_index"
