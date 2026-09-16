"""Tests for the protocluster search HTTP layer.

Covers request parsing (:func:`parse_search_request`), the per-level response
dataclasses that wrap the core result types with the pagination envelope, the
structured error mapping, and the Flask ``POST /api/search/<level>`` routes.
"""

import json

import pytest
from bgc_viewer.app import (
    MissingDatabaseError,
    NoDatabaseError,
    app,
)
from bgc_viewer.search.api import (
    MAX_PAGE_SIZE,
    DEFAULT_PAGE_SIZE,
    InvalidRequestError,
    ProtoclusterResponse,
    RecordResponse,
    RegionResponse,
    SearchRequest,
    error_response,
    parse_search_request,
)
from bgc_viewer.search.document import (
    SEARCH_FIELD_REGISTRY,
    Location,
    ProtoclusterSearchDocument,
    SearchFields,
    SourceFile,
)
from bgc_viewer.search.index import (
    EmptyQueryError,
    IndexCorruptError,
    IndexIncompatibleError,
    IndexNotFoundError,
    QuerySyntaxError,
    UnknownFieldError,
    build_index,
    open_index,
    search_protoclusters,
    search_record,
    search_region,
)


def _doc(
    protocluster_number: int,
    *,
    record_id: str = "recA",
    region_number: int = 1,
    location: str = "[100:500](+)",
    product: str = "NRP",
    category: str = "NRPS",
    organism: str = "His Kinase Amycolatopsis",
    pfam: tuple[str, ...] = (),
) -> ProtoclusterSearchDocument:
    return ProtoclusterSearchDocument(
        source=SourceFile("8.0.2", "rec.json", "rec.json", "rec.gbk"),
        search_fields=SearchFields(
            record_id=record_id,
            region_number=region_number,
            protocluster_number=protocluster_number,
            location=Location.parse(location),
            product=product,
            category=category,
            organism=organism,
            pfam=pfam,
            pfam_name=(),
            gene=(),
            locus=(),
        ),
    )


@pytest.fixture
def grouped_corpus() -> list[ProtoclusterSearchDocument]:
    return [
        _doc(1, record_id="recA", region_number=1, pfam=("shared",)),
        _doc(2, record_id="recA", region_number=1, pfam=("shared",)),
        _doc(1, record_id="recA", region_number=2, pfam=("shared",)),
        _doc(1, record_id="recB", region_number=1, pfam=("shared",)),
    ]


@pytest.fixture
def index_dir(grouped_corpus, tmp_path) -> str:
    target = tmp_path / "tantivy.index"
    build_index(iter(grouped_corpus), target)
    return str(target)


class TestParseSearchRequest:
    def test_defaults(self):
        req = parse_search_request({"query": "pfam:shared"})
        assert req == SearchRequest(query="pfam:shared", page=1, per_page=20)
        assert req.offset == 0

    def test_offset_is_derived_from_page_and_per_page(self):
        req = parse_search_request({"query": "q", "page": 3, "per_page": 15})
        assert req.offset == 30

    def test_per_page_clamped_to_maximum(self):
        req = parse_search_request({"query": "q", "per_page": 500})
        assert req.per_page == MAX_PAGE_SIZE

    def test_non_object_body_rejected(self):
        for body in (None, [], "text", 5):
            with pytest.raises(InvalidRequestError):
                parse_search_request(body)

    def test_non_string_query_rejected(self):
        with pytest.raises(InvalidRequestError):
            parse_search_request({"query": 123})

    def test_non_integer_pagination_rejected(self):
        with pytest.raises(InvalidRequestError):
            parse_search_request({"query": "q", "page": "x"})

    def test_page_below_one_rejected(self):
        with pytest.raises(InvalidRequestError):
            parse_search_request({"query": "q", "page": 0})

    def test_per_page_below_one_rejected(self):
        with pytest.raises(InvalidRequestError):
            parse_search_request({"query": "q", "per_page": 0})


class TestResponseFromResults:
    def test_protocluster_response_wraps_results_with_envelope(self, index_dir):
        request = SearchRequest(query="pfam:shared", page=1, per_page=2)
        results = search_protoclusters(
            open_index(index_dir), "pfam:shared", offset=0, limit=2
        )
        response = ProtoclusterResponse.from_results(results, request)
        assert response.level == "protocluster"
        assert response.query == "pfam:shared"
        assert response.total == 4
        assert response.total_pages == 2
        assert response.page == 1
        assert response.per_page == 2
        assert len(response.hits) == 2

    def test_region_response_total_pages_math(self, index_dir):
        request = SearchRequest(query="pfam:shared", page=1, per_page=2)
        results = search_region(open_index(index_dir), "pfam:shared", offset=0, limit=2)
        response = RegionResponse.from_results(results, request)
        assert response.level == "region"
        assert response.total == 3
        assert response.total_pages == 2

    def test_record_response_zero_total_reports_zero_pages(self, index_dir):
        request = SearchRequest(query="pfam:none", page=1, per_page=20)
        results = search_record(open_index(index_dir), "pfam:none", offset=0, limit=20)
        response = RecordResponse.from_results(results, request)
        assert response.total == 0
        assert response.total_pages == 0
        assert response.hits == ()


class TestErrorResponse:
    def test_unknown_field_includes_available_fields(self):
        payload, status = error_response(UnknownFieldError("go", ["organism", "pfam"]))
        assert status == 400
        assert payload["error"]["code"] == "unknown_field"
        assert payload["error"]["details"]["available_fields"] == ["organism", "pfam"]

    @pytest.mark.parametrize(
        "error, status",
        [
            (EmptyQueryError(), 400),
            (QuerySyntaxError("bad"), 400),
            (NoDatabaseError(), 400),
            (MissingDatabaseError("/nope.db"), 404),
            (IndexNotFoundError("none"), 404),
            (IndexIncompatibleError("bad"), 409),
            (IndexCorruptError("bad"), 500),
        ],
    )
    def test_search_error_status_mapping(self, error, status):
        payload, got = error_response(error)
        assert got == status
        assert payload["error"]["code"] == error.code

    def test_unexpected_error_is_500(self):
        payload, status = error_response(RuntimeError("boom"))
        assert status == 500
        assert payload["error"]["code"] == "search_failed"


@pytest.fixture
def search_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _select_database(client, db_path):
    with client.session_transaction() as sess:
        sess["current_database_path"] = str(db_path)


class TestSearchEndpoint:
    def test_protocluster_endpoint_json_shape(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/protocluster", json={"query": "pfam:PF00501"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert set(data) == {
            "query",
            "level",
            "page",
            "per_page",
            "total",
            "total_pages",
            "offset",
            "limit",
            "hits",
        }
        assert data["level"] == "protocluster"
        assert data["total"] == 2
        assert set(data["hits"][0]) == {"score", "fields"}
        assert data["hits"][0]["fields"]["record"] in {"test_record_1", "test_record_2"}

    def test_region_endpoint_json_shape(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/region", json={"query": "pfam:PF00501"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["level"] == "region"
        assert data["total"] == 2
        assert set(data["hits"][0]) == {
            "score",
            "record",
            "region",
            "output_file",
            "input_file",
        }

    def test_record_endpoint_json_shape(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/record", json={"query": "pfam:PF00501"}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["level"] == "record"
        assert data["total"] == 2
        assert set(data["hits"][0]) == {"score", "record", "output_file", "input_file"}

    def test_pagination_flows_through_response(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/protocluster",
            json={"query": "pfam:PF00501", "page": 1, "per_page": 1},
        )
        data = json.loads(response.data)
        assert data["page"] == 1
        assert data["per_page"] == 1
        assert data["total"] == 2
        assert data["total_pages"] == 2
        assert data["offset"] == 0
        assert len(data["hits"]) == 1

    def test_unknown_level_is_not_a_route(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/bogus", json={"query": "pfam:PF00501"}
        )
        # No dedicated unknown-level handler: the GET-only SPA fallback matches
        # the path but rejects POST, so Flask answers 405 Method Not Allowed.
        assert response.status_code == 405

    def test_invalid_body_returns_400(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post("/api/search/record", json={"query": 123})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"]["code"] == "invalid_request"

    def test_no_database_selected_returns_400(self, search_client):
        response = search_client.post(
            "/api/search/protocluster", json={"query": "pfam:PF00501"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"]["code"] == "no_database"

    def test_missing_index_returns_404(self, search_client, temp_dir):
        empty_db = temp_dir / "attributes.db"
        empty_db.write_text("")
        _select_database(search_client, empty_db)
        response = search_client.post(
            "/api/search/protocluster", json={"query": "pfam:PF00501"}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"]["code"] == "missing_index"

    def test_unknown_field_returns_400(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/protocluster", json={"query": "go:x"}
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"]["code"] == "unknown_field"
        assert data["error"]["details"]["available_fields"] == sorted(
            definition.name for definition in SEARCH_FIELD_REGISTRY
        )
