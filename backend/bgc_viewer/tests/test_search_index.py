"""Tests for the embedded Tantivy record index."""

from bgc_viewer.search_index import (
    create_search_index,
    make_search_document,
    search_record_ids,
)


def test_record_level_search_uses_deep_attribute_values(temp_dir):
    db_path = temp_dir / "attributes.db"
    index = create_search_index(db_path)
    writer = index.writer()
    writer.add_document(
        make_search_document(
            7,
            "NC_003888.3",
            "NC_003888.3.json",
            {
                "modules": {"deep": {"db_xref": "PF00067.25"}},
                "features": [{"qualifiers": {"organism": "Streptomyces test"}}],
                "seq": "PF00067.25 must not be indexed from sequence data",
            },
        )
    )
    writer.add_document(
        make_search_document(
            8,
            "other_record",
            "other.json",
            {"features": [{"qualifiers": {"organism": "Streptomyces test"}}]},
        )
    )
    writer.commit()

    record_ids, total = search_record_ids(db_path, "PF00067.25 Streptomyces", 10)

    assert record_ids == [7]
    assert total == 1

    record_ids, total = search_record_ids(db_path, "sequence data", 10)

    assert record_ids == []
    assert total == 0
