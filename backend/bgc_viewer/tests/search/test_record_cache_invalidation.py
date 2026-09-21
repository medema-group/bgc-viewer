"""Tests for record-data cache invalidation across an in-place rebuild.

Stage 2 step 8 keeps the record-data LRU cache from serving a corpus that no
longer exists. ``load_cached_entry`` is keyed by the database build generation
as well as the path: ``populate_metadata_table()`` rewrites the timestamp on
every preprocessing run, so an in-place rebuild at the same path makes the
entries cached from the deleted build unreachable.

The generation is not incidental. A rebuild rewrites both the record JSON that
is parsed and the byte offsets the parser reads from the database, so an entry
cached from the previous build is wrong content, not merely old content. The
token is read from the live database on every request, which also means the
previous generation disappears the moment the rebuild deletes the old file.
"""

from __future__ import annotations

import json

import pytest
from bgc_viewer.app import load_cached_entry, record_cache_build_id
from bgc_viewer.database import get_database_info
from bgc_viewer.preprocessing import populate_metadata_table
from bgc_viewer.preprocessing import preprocess_antismash_files

ENTRY_ID = "sample.json:recA"


def _source(region_end: int) -> dict:
    """A minimal antiSMASH 8 file whose region extent is easy to vary."""
    return {
        "version": "8.0.2",
        "input_file": "sample.gbk",
        "records": [
            {
                "id": "recA",
                "features": [
                    {
                        "type": "region",
                        "location": f"[1:{region_end}]",
                        "qualifiers": {"region_number": ["1"]},
                    },
                    {
                        "type": "gene",
                        "location": f"[100:{region_end - 100}]",
                        "qualifiers": {"gene": ["hglE-KS"]},
                    },
                    {
                        "type": "protocluster",
                        "location": f"[50:{region_end - 50}]",
                        "qualifiers": {
                            "protocluster_number": ["1"],
                            "category": ["PKS"],
                            "product": ["NRP"],
                        },
                    },
                ],
            }
        ],
    }


def _write_source(temp_dir, region_end: int):
    path = temp_dir / "sample.json"
    path.write_text(json.dumps(_source(region_end)), encoding="utf-8")
    return path


def _rebuild(temp_dir):
    return preprocess_antismash_files(str(temp_dir), str(temp_dir / "attributes.db"))


def _region_location(data: dict) -> str:
    record = data["records"][0]
    region = next(f for f in record["features"] if f["type"] == "region")
    return region["location"]


@pytest.fixture
def built(temp_dir):
    """A preprocessed folder plus the generation its database reports."""
    _write_source(temp_dir, 1000)
    _rebuild(temp_dir)
    db_path = temp_dir / "attributes.db"
    return temp_dir, db_path, record_cache_build_id(str(db_path))


class TestBuildGeneration:
    def test_a_built_database_reports_a_generation(self, built):
        _, db_path, build_id = built
        assert build_id

    def test_a_rebuild_at_the_same_path_produces_a_new_generation(self, temp_dir):
        _write_source(temp_dir, 1000)
        _rebuild(temp_dir)
        db_path = temp_dir / "attributes.db"
        first = record_cache_build_id(str(db_path))

        _write_source(temp_dir, 2000)
        _rebuild(temp_dir)
        second = record_cache_build_id(str(db_path))

        assert second != first

    def test_the_generation_comes_from_the_database_metadata(self, built):
        _, db_path, build_id = built
        assert get_database_info(str(db_path))["build_id"] == build_id

    def test_an_unreadable_database_reports_no_generation(self, temp_dir):
        assert record_cache_build_id(str(temp_dir / "missing.db")) == ""

    def test_a_database_without_timestamp_metadata_falls_back_to_the_file(
        self, temp_dir
    ):
        db_path = temp_dir / "attributes.db"
        _write_source(temp_dir, 1000)
        _rebuild(temp_dir)
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            "DELETE FROM metadata WHERE key IN ('modified_date', 'creation_date')"
        )
        conn.commit()
        conn.close()

        build_id = record_cache_build_id(str(db_path))
        assert build_id == str(db_path.stat().st_mtime_ns)


class TestGenerationIsPartOfTheCacheKey:
    def test_the_same_generation_reuses_the_cached_object(self, built):
        temp_dir, db_path, build_id = built
        first = load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), build_id)
        assert (
            load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), build_id) is first
        )

    def test_a_new_generation_does_not_reuse_the_previous_object(self, built):
        temp_dir, db_path, stale_id = built
        stale = load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), stale_id)

        _write_source(temp_dir, 2000)
        _rebuild(temp_dir)
        fresh_id = record_cache_build_id(str(db_path))

        fresh = load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), fresh_id)

        assert fresh is not stale
        assert _region_location(fresh) == "[1:2000]"
        assert _region_location(stale) == "[1:1000]"

    def test_the_stale_object_is_only_reachable_with_the_stale_generation(self, built):
        """Why the token must be read from the live database, never remembered.

        The cache itself cannot tell a stale generation from a current one, so a
        caller that cached the token would resurrect the deleted build's data.
        """
        temp_dir, db_path, stale_id = built
        stale = load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), stale_id)

        _write_source(temp_dir, 2000)
        _rebuild(temp_dir)

        assert record_cache_build_id(str(db_path)) != stale_id
        assert (
            load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), stale_id) is stale
        )

    def test_a_new_generation_is_a_cache_miss_not_a_hit(self, built):
        temp_dir, db_path, first_id = built
        load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), first_id)

        misses_before = load_cached_entry.cache_info().misses
        load_cached_entry(ENTRY_ID, str(db_path), str(temp_dir), "another-generation")
        assert load_cached_entry.cache_info().misses == misses_before + 1


class TestRebuildWindow:
    def test_the_previous_generation_is_unreachable_during_the_window(
        self, monkeypatch, built
    ):
        """Invalidation starts at the destructive delete, not at the commit.

        ``create_attributes_database()`` unlinks the previous database before
        any new metadata exists, so a request landing inside the window cannot
        resolve the generation it would need to reach a cached entry.
        """
        temp_dir, db_path, previous_id = built
        seen: dict[str, str] = {}
        real = populate_metadata_table

        def spy(conn, data_root):
            seen["generation"] = record_cache_build_id(str(db_path))
            return real(conn, data_root)

        monkeypatch.setattr("bgc_viewer.preprocessing.populate_metadata_table", spy)
        _write_source(temp_dir, 2000)
        _rebuild(temp_dir)

        assert seen["generation"] == ""
        assert seen["generation"] != previous_id

    def test_the_new_generation_is_live_as_soon_as_the_build_completes(self, temp_dir):
        _write_source(temp_dir, 1000)
        _rebuild(temp_dir)
        db_path = temp_dir / "attributes.db"

        _write_source(temp_dir, 3000)
        _rebuild(temp_dir)

        data = load_cached_entry(
            ENTRY_ID, str(db_path), str(temp_dir), record_cache_build_id(str(db_path))
        )
        assert _region_location(data) == "[1:3000]"


class TestRecordBrowsingThroughTheApp:
    @pytest.fixture
    def browsing_client(self, client, built):
        temp_dir, db_path, _ = built
        with client.session_transaction() as sess:
            sess["current_database_path"] = str(db_path)
            sess["loaded_entry_id"] = ENTRY_ID
        return client, temp_dir, db_path

    def test_record_browsing_reflects_a_rebuild_of_the_same_path(self, browsing_client):
        client, temp_dir, db_path = browsing_client

        first = client.get("/api/records/recA/regions")
        assert first.status_code == 200
        assert first.get_json()["regions"][0]["end"] == 1000

        _write_source(temp_dir, 2000)
        _rebuild(temp_dir)

        second = client.get("/api/records/recA/regions")
        assert second.status_code == 200
        assert second.get_json()["regions"][0]["end"] == 2000

    def test_load_entry_primes_the_cache_of_the_current_generation(
        self, browsing_client, monkeypatch
    ):
        client, temp_dir, db_path = browsing_client
        calls: list[tuple] = []
        real = load_cached_entry.__wrapped__

        def spy(*args):
            calls.append(args)
            return real(*args)

        monkeypatch.setattr("bgc_viewer.app.load_cached_entry", spy)
        response = client.post("/api/load-entry", json={"id": ENTRY_ID})

        assert response.status_code == 200
        assert calls == [
            (ENTRY_ID, str(db_path), str(temp_dir), record_cache_build_id(str(db_path)))
        ]

    def test_record_browsing_survives_a_rebuild_while_holding_a_stale_session(
        self, browsing_client
    ):
        """A session that loaded an entry before the rebuild must not pin it."""
        client, temp_dir, db_path = browsing_client
        assert client.get("/api/records/recA/regions").status_code == 200

        _write_source(temp_dir, 4000)
        _rebuild(temp_dir)

        regions = client.get("/api/records/recA/regions").get_json()["regions"]
        assert regions[0]["end"] == 4000
