"""Tests for the request-scoped search reader lifecycle.

Stage 2 step 4 keeps every Tantivy handle request-scoped: each search request
opens its own index, and nothing retains a reader, a file descriptor, or a
memory mapping once the request returns. A rebuild deletes ``tantivy.index/``
in place, so a cached handle would pin the deleted segments and keep serving
the previous corpus after the same path is rebuilt from different files.

The level-independent ``GET /api/search/schema`` endpoint opens a handle
purely for availability signaling, so it is held to the same invariants.
"""

from __future__ import annotations

import gc
import json
import os
import shutil
from pathlib import Path

import pytest
import bgc_viewer.app as app_module
from bgc_viewer.app import app
from bgc_viewer.search.document import Location
from bgc_viewer.search.index import (
    build_index,
    open_index,
    search_protoclusters,
)
from tantivy import Index
from tantivy import Document

LEVELS = ("protocluster", "region", "record")
_PROC = Path("/proc/self")

linux_only = pytest.mark.skipif(
    not (_PROC / "fd").is_dir() and not (_PROC / "maps").is_file(),
    reason="descriptor and mapping scan requires Linux",
)


def _is_under(path: str, root: Path) -> bool:
    try:
        return Path(path).is_relative_to(root)
    except ValueError:
        return False


def _pinned(root: Path) -> set[str]:
    """Return every path under ``root`` this process still pins.

    A live Tantivy handle pins its index files through memory mappings and the
    Tantivy meta lock through a descriptor. Deleted-but-still-mapped files keep
    the `` (deleted)`` suffix ``/proc`` appends, so they are reported too.
    """
    root = root.resolve()
    pinned: set[str] = set()
    for entry in os.listdir(_PROC / "fd"):
        try:
            target = os.readlink(_PROC / "fd" / entry)
        except OSError:
            continue
        if _is_under(target, root):
            pinned.add(target)
    with (_PROC / "maps").open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.split(maxsplit=5)
            if len(fields) < 6:
                continue
            path = fields[5].strip()
            if _is_under(path, root):
                pinned.add(path)
    return pinned


def _doc(
    protocluster_number: int,
    *,
    record_id: str = "recA",
    region_number: int = 1,
    pfam: tuple[str, ...] = ("PF00501",),
) -> Document:
    location = Location.parse("[100:500](+)")
    document = Document()
    document.add_text("record", record_id)
    document.add_integer("region", region_number)
    document.add_integer("protocluster", protocluster_number)
    document.add_integer("start", location.start)
    document.add_integer("end", location.end)
    document.add_text("product", "NRP")
    document.add_text("category", "NRPS")
    document.add_text("organism", "His Kinase Amycolatopsis")
    for value in pfam:
        document.add_text("pfam", value)
    document.add_text("output_file", "rec.json")
    document.add_text("input_file", "rec.gbk")
    return document


@pytest.fixture
def search_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _select_database(client, db_path) -> None:
    with client.session_transaction() as sess:
        sess["current_database_path"] = str(db_path)


def _search(client, level: str, query: str = "pfam:PF00501", **extra):
    return client.post(f"/api/search/{level}", json={"query": query, **extra})


def _index_dir(db_path: Path) -> Path:
    return db_path.parent / "tantivy.index"


def _counting_open(recorder: list):
    """Wrap the module's ``open_index`` so every call is recorded and counted."""
    real = app_module.open_index

    def counting(path):
        opened = real(path)
        recorder.append(opened)
        return opened

    return counting


def _retained_handles(namespace: dict) -> list[str]:
    """Names in ``namespace`` that reach a live search index handle, one level deep.

    Looking inside containers catches a handle cached as a tuple or dict value,
    not just one bound directly to a module or ``app`` attribute.
    """
    retained: list[str] = []
    for name, value in namespace.items():
        if isinstance(value, Index):
            retained.append(name)
            continue
        if isinstance(value, dict):
            members: tuple = tuple(value.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            members = tuple(value)
        else:
            members = ()
        if any(isinstance(member, Index) for member in members):
            retained.append(name)
    return retained


class TestOpenPerRequest:
    @pytest.mark.parametrize("level", LEVELS)
    def test_every_search_request_opens_its_own_handle(
        self, search_client, test_database, monkeypatch, level
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        opens: list = []
        monkeypatch.setattr(app_module, "open_index", _counting_open(opens))

        for _ in range(3):
            assert _search(search_client, level).status_code == 200

        assert len(opens) == 3
        assert len({id(handle) for handle in opens}) == 3

    def test_malformed_request_opens_no_handle(
        self, search_client, temp_dir, monkeypatch
    ):
        """A request that never searches must not touch the index on disk."""
        database = temp_dir / "attributes.db"
        database.write_text("")
        _select_database(search_client, database)
        opens: list = []
        monkeypatch.setattr(app_module, "open_index", _counting_open(opens))

        response = _search(search_client, "protocluster", query=123)

        assert response.status_code == 400
        assert json.loads(response.data)["error"]["code"] == "invalid_request"
        assert opens == []

    def test_no_handle_is_retained_on_the_app_or_module(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        for level in LEVELS:
            assert _search(search_client, level).status_code == 200

        gc.collect()
        assert _retained_handles(vars(app_module)) == []
        assert _retained_handles(vars(app)) == []


class TestRebuildVisibility:
    def test_a_rebuilt_index_is_visible_without_invalidation(
        self, search_client, test_database
    ):
        """Reopening per request makes an in-place rebuild visible with no cache flush."""
        db_path, _ = test_database
        _select_database(search_client, db_path)
        index_dir = _index_dir(db_path)

        first = json.loads(_search(search_client, "protocluster").data)
        assert len(first["hits"]) == 2

        shutil.rmtree(index_dir)
        build_index(
            iter(
                [
                    _doc(1, record_id="recX"),
                    _doc(2, record_id="recX"),
                    _doc(1, record_id="recY", region_number=2),
                ]
            ),
            index_dir,
        )

        second = json.loads(_search(search_client, "protocluster").data)
        assert len(second["hits"]) == 3
        assert {hit["fields"]["record"] for hit in second["hits"]} == {"recX", "recY"}

    def test_a_deleted_index_is_reported_instead_of_served_from_a_stale_reader(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        assert _search(search_client, "protocluster").status_code == 200

        shutil.rmtree(_index_dir(db_path))

        response = _search(search_client, "protocluster")
        assert response.status_code == 404
        assert json.loads(response.data)["error"]["code"] == "missing_index"


@linux_only
class TestNothingPinnedAfterRequest:
    def test_a_live_handle_really_pins_the_index_directory(self, test_database):
        """Control: the scan detects a live handle, so the release tests are not vacuous."""
        db_path, _ = test_database
        index_dir = _index_dir(db_path)
        handle = open_index(index_dir)
        search_protoclusters(handle, "pfam:PF00501", offset=0, limit=5)
        assert _pinned(index_dir)

        del handle
        gc.collect()
        assert _pinned(index_dir) == set()

    @pytest.mark.parametrize("level", LEVELS)
    def test_successful_search_leaves_nothing_pinned(
        self, search_client, test_database, level
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        index_dir = _index_dir(db_path)

        assert _search(search_client, level, query="pfam:PF00501").status_code == 200

        gc.collect()
        assert _pinned(index_dir) == set()

    def test_failed_search_leaves_nothing_pinned(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        index_dir = _index_dir(db_path)

        assert _search(search_client, "protocluster", query="go:x").status_code == 400

        gc.collect()
        assert _pinned(index_dir) == set()

    def test_a_rebuild_can_delete_the_directory_after_requests(
        self, search_client, test_database
    ):
        """Deleting the index after serving requests must not leave deleted files pinned."""
        db_path, _ = test_database
        _select_database(search_client, db_path)
        index_dir = _index_dir(db_path)
        for level in LEVELS:
            assert (
                _search(search_client, level, query="pfam:PF00501").status_code == 200
            )

        gc.collect()
        shutil.rmtree(index_dir)

        assert not index_dir.exists()
        assert _pinned(index_dir) == set()


class TestSchemaEndpointLifecycle:
    """The schema endpoint opens a handle, so the same rules apply to it."""

    def test_every_schema_request_opens_its_own_handle(
        self, search_client, test_database, monkeypatch
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        opens: list = []
        monkeypatch.setattr(app_module, "open_index", _counting_open(opens))

        for _ in range(3):
            assert search_client.get("/api/search/schema").status_code == 200

        assert len(opens) == 3
        assert len({id(handle) for handle in opens}) == 3

    def test_no_handle_is_retained_after_schema_requests(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        for _ in range(2):
            assert search_client.get("/api/search/schema").status_code == 200

        gc.collect()
        assert _retained_handles(vars(app_module)) == []
        assert _retained_handles(vars(app)) == []

    @linux_only
    def test_successful_schema_request_leaves_nothing_pinned(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        index_dir = _index_dir(db_path)

        assert search_client.get("/api/search/schema").status_code == 200

        gc.collect()
        assert _pinned(index_dir) == set()

    @linux_only
    def test_failed_schema_request_leaves_nothing_pinned(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        index_dir = _index_dir(db_path)
        (index_dir / "version.txt").write_text("999", encoding="utf-8")

        assert search_client.get("/api/search/schema").status_code == 409

        gc.collect()
        assert _pinned(index_dir) == set()


class TestSqliteBrowsingWithoutIndex:
    def test_record_browsing_works_with_no_search_index(self, client, test_database):
        db_path, _ = test_database
        shutil.rmtree(_index_dir(db_path))
        _select_database(client, db_path)

        response = client.get("/api/database-entries?page=1&per_page=10")

        assert response.status_code == 200
        assert json.loads(response.data)["total"] >= 2

    def test_record_browsing_works_with_an_unreadable_search_index(
        self, client, test_database
    ):
        db_path, _ = test_database
        index_dir = _index_dir(db_path)
        shutil.rmtree(index_dir)
        index_dir.mkdir()
        (index_dir / "meta.json").write_text("{ not json", encoding="utf-8")
        _select_database(client, db_path)

        response = client.get("/api/database-entries?page=1&per_page=10")

        assert response.status_code == 200
        assert json.loads(response.data)["total"] >= 2
