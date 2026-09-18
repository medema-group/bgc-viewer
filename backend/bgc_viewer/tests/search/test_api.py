"""Tests for the protocluster search HTTP layer.

Covers request parsing (:func:`parse_search_request`), the minimal
:class:`SearchResponse` body built from the core result types, the structured
error mapping, the Flask ``POST /api/search/<level>`` routes, and the
level-independent ``GET /api/search/schema`` endpoint.
"""

import json
import sqlite3

import pytest
import bgc_viewer.app as app_module
from bgc_viewer.app import (
    MissingDatabaseError,
    NoDatabaseError,
    app,
)
from bgc_viewer.search.api import (
    MAX_PAGE_SIZE,
    QUERY_SYNTAX_URL,
    InvalidRequestError,
    SearchRequest,
    SearchResponse,
    build_schema_response,
    error_response,
    parse_search_request,
    read_example_queries,
)
from bgc_viewer.search.build_state import mark_building
from bgc_viewer.search.document import (
    SEARCH_FIELD_REGISTRY,
    SEARCH_SCHEMA_VERSION,
    Location,
    ProtoclusterSearchDocument,
    SearchFieldDefinition,
    SearchFields,
    SourceFile,
    public_field_metadata,
    public_kind,
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
    def test_response_carries_only_hits_and_total(self, index_dir):
        results = search_protoclusters(
            open_index(index_dir), "pfam:shared", offset=0, limit=2
        )
        response = SearchResponse.from_results(results)
        assert response.total == 4
        assert len(response.hits) == 2

    def test_region_response_total_counts_distinct_regions(self, index_dir):
        results = search_region(open_index(index_dir), "pfam:shared", offset=0, limit=2)
        response = SearchResponse.from_results(results)
        assert response.total == 3

    def test_record_response_zero_total_reports_no_hits(self, index_dir):
        results = search_record(open_index(index_dir), "pfam:none", offset=0, limit=20)
        response = SearchResponse.from_results(results)
        assert response.total == 0
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
        assert set(data) == {"hits", "total"}
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
        assert set(data) == {"hits", "total"}
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
        assert set(data) == {"hits", "total"}
        assert data["total"] == 2
        assert set(data["hits"][0]) == {"score", "record", "output_file", "input_file"}

    def test_pagination_limits_hits_without_echoing_request(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = search_client.post(
            "/api/search/protocluster",
            json={"query": "pfam:PF00501", "page": 1, "per_page": 1},
        )
        data = json.loads(response.data)
        assert set(data) == {"hits", "total"}
        assert data["total"] == 2
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


# --- Public field projection -------------------------------------------------


def _definition(**overrides) -> SearchFieldDefinition:
    fields = dict(
        name="go",
        description="Gene Ontology term of the protocluster.",
        attribute="go",
        value_type="keyword",
        cardinality="multi",
        analyzer="exact",
        returned=False,
        default_search=True,
        boost=2.0,
        required=False,
    )
    fields.update(overrides)
    return SearchFieldDefinition(**fields)


class TestPublicFieldProjection:
    def test_every_registered_field_is_projected_in_registry_order(self):
        projected = public_field_metadata()
        assert [info.name for info in projected] == [
            definition.name for definition in SEARCH_FIELD_REGISTRY
        ]

    def test_kind_comes_from_the_analyzer_for_text_fields(self):
        kinds = {info.name: info.kind for info in public_field_metadata()}
        assert kinds["pfam"] == "exact"
        assert kinds["product"] == "exact"
        assert kinds["output_file"] == "exact"
        assert kinds["organism"] == "full_text"
        assert kinds["pfam_name"] == "full_text"

    def test_kind_is_numeric_for_fields_without_an_analyzer(self):
        kinds = {info.name: info.kind for info in public_field_metadata()}
        for name in ("region", "protocluster", "start", "end"):
            assert kinds[name] == "numeric", name

    def test_unqualified_mirrors_the_registry_default_search_flag(self):
        projected = {info.name: info for info in public_field_metadata()}
        for definition in SEARCH_FIELD_REGISTRY:
            assert projected[definition.name].unqualified == definition.default_search

    def test_no_numeric_field_participates_in_unqualified_search(self):
        assert [
            info.name
            for info in public_field_metadata()
            if info.kind == "numeric" and info.unqualified
        ] == []

    def test_every_field_carries_a_non_empty_description(self):
        empty = [
            info.name
            for info in public_field_metadata()
            if not info.description.strip()
        ]
        assert empty == []

    def test_public_kind_rejects_a_text_field_with_no_analyzer(self):
        with pytest.raises(ValueError, match="no user-facing kind"):
            public_kind(_definition(value_type="keyword", analyzer=None))


# --- Example reads -----------------------------------------------------------


def _example_queries(db_path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            row[0]
            for row in conn.execute(
                "SELECT query FROM search_examples ORDER BY id"
            ).fetchall()
        ]
    finally:
        conn.close()


def _database_without_example_table(db_path) -> None:
    """Create a database that has no ``search_examples`` table at all."""
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()


class TestReadExampleQueries:
    def test_reads_rows_in_the_order_preprocessing_wrote_them(self, test_database):
        db_path, _ = test_database
        assert list(read_example_queries(db_path)) == _example_queries(db_path)

    def test_missing_table_yields_no_examples(self, temp_dir):
        database = temp_dir / "attributes.db"
        _database_without_example_table(database)
        assert read_example_queries(database) == ()

    def test_build_schema_response_pairs_registry_fields_with_stored_examples(
        self, test_database
    ):
        db_path, _ = test_database
        response = build_schema_response(db_path)
        assert [info.name for info in response.fields] == [
            definition.name for definition in SEARCH_FIELD_REGISTRY
        ]
        assert list(response.examples) == _example_queries(db_path)
        assert response.query_syntax_url == QUERY_SYNTAX_URL


# --- Schema endpoint ---------------------------------------------------------


def _schema(search_client):
    return search_client.get("/api/search/schema")


SAMPLE_EXAMPLES = [
    "PF00501",
    "category:PKS",
    '"Streptomyces coelicolor"',
    "category:PKS AND product:polyketide",
    'organism:"Streptomyces coelicolor" NOT product:polyketide',
]


class TestSchemaEndpoint:
    def test_response_carries_exactly_fields_examples_and_syntax_url(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        response = _schema(search_client)
        assert response.status_code == 200
        assert set(json.loads(response.data)) == {
            "fields",
            "examples",
            "query_syntax_url",
        }

    def test_field_objects_expose_only_the_public_keys(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        data = json.loads(_schema(search_client).data)
        for field in data["fields"]:
            assert set(field) == {"name", "kind", "unqualified", "description"}

    def test_internal_registry_details_are_not_exposed(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        data = json.loads(_schema(search_client).data)
        for field in data["fields"]:
            for internal in ("boost", "cardinality", "stored", "returned", "analyzer"):
                assert internal not in field, f"{internal} leaked via {field['name']}"

    def test_fields_cover_the_whole_registry_in_order(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        data = json.loads(_schema(search_client).data)
        assert [field["name"] for field in data["fields"]] == [
            definition.name for definition in SEARCH_FIELD_REGISTRY
        ]

    def test_examples_are_the_generated_queries_in_template_order(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        data = json.loads(_schema(search_client).data)
        assert data["examples"] == SAMPLE_EXAMPLES

    def test_query_syntax_url_is_the_generic_latest_parser_link(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        data = json.loads(_schema(search_client).data)
        assert data["query_syntax_url"] == (
            "https://docs.rs/tantivy/latest/tantivy/query/struct.QueryParser.html"
        )
        assert "0.26" not in data["query_syntax_url"]

    def test_response_carries_no_level(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        assert "level" not in json.loads(_schema(search_client).data)

    def test_repeated_requests_are_identical(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        assert _schema(search_client).data == _schema(search_client).data

    def test_post_is_not_allowed(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        assert search_client.post("/api/search/schema", json={}).status_code == 405

    def test_the_index_is_opened_only_for_availability_signaling(
        self, search_client, test_database, monkeypatch
    ):
        """A stub handle still yields a complete response: nothing is read from it."""
        db_path, _ = test_database
        _select_database(search_client, db_path)
        opened: list = []
        monkeypatch.setattr(
            app_module, "open_index", lambda path: opened.append(path) or object()
        )

        response = _schema(search_client)

        assert response.status_code == 200
        assert opened == [str(db_path.parent / "tantivy.index")]
        data = json.loads(response.data)
        assert len(data["fields"]) == len(SEARCH_FIELD_REGISTRY)
        assert data["examples"] == SAMPLE_EXAMPLES

    def test_no_database_selected_returns_400(self, search_client):
        response = _schema(search_client)
        assert response.status_code == 400
        assert json.loads(response.data)["error"]["code"] == "no_database"

    def test_missing_database_file_returns_404(self, search_client, temp_dir):
        _select_database(search_client, temp_dir / "gone.db")
        response = _schema(search_client)
        assert response.status_code == 404
        assert json.loads(response.data)["error"]["code"] == "missing_database"

    def test_missing_index_returns_404(self, search_client, temp_dir):
        database = temp_dir / "attributes.db"
        database.write_text("")
        _select_database(search_client, database)
        response = _schema(search_client)
        assert response.status_code == 404
        assert json.loads(response.data)["error"]["code"] == "missing_index"

    def test_incompatible_schema_returns_409(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        meta_path = db_path.parent / "tantivy.index" / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["payload"] = json.dumps(
            {"search_schema_version": SEARCH_SCHEMA_VERSION + 1}
        )
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        response = _schema(search_client)
        assert response.status_code == 409
        assert json.loads(response.data)["error"]["code"] == "incompatible_schema"

    def test_live_build_returns_409_rebuilding(
        self, monkeypatch, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        monkeypatch.setitem(app_module.PREPROCESSING_STATUS, "is_running", True)
        response = _schema(search_client)
        assert response.status_code == 409
        assert json.loads(response.data)["error"]["code"] == "index_rebuilding"

    def test_stale_sentinel_returns_409_interrupted(self, search_client, test_database):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        mark_building(db_path.parent)
        response = _schema(search_client)
        assert response.status_code == 409
        assert json.loads(response.data)["error"]["code"] == "index_interrupted"

    def test_guard_runs_before_any_handle_is_opened(
        self, search_client, test_database, monkeypatch
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        opened: list = []
        monkeypatch.setattr(app_module, "open_index", lambda path: opened.append(path))
        mark_building(db_path.parent)

        assert _schema(search_client).status_code == 409
        assert opened == []

    def test_a_read_request_does_not_clear_a_stale_sentinel(
        self, search_client, test_database
    ):
        db_path, _ = test_database
        _select_database(search_client, db_path)
        mark_building(db_path.parent)
        _schema(search_client)
        from bgc_viewer.search.build_state import is_building

        assert is_building(db_path.parent)

    def test_fields_are_served_when_the_example_table_is_absent(
        self, search_client, temp_dir
    ):
        """A database without examples still gets the full registry-driven fields."""
        database = temp_dir / "attributes.db"
        _database_without_example_table(database)
        build_index(iter([_doc(1)]), temp_dir / "tantivy.index")
        _select_database(search_client, database)

        response = _schema(search_client)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["examples"] == []
        assert len(data["fields"]) == len(SEARCH_FIELD_REGISTRY)
