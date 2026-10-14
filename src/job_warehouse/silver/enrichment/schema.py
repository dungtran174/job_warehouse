"""Typed one-to-one enrichment sidecar, with evidence offsets in clean fields."""

import pyarrow as pa


def enrichment_schema() -> pa.Schema:
    evidence = pa.struct(
        [
            pa.field("field", pa.string(), nullable=False),
            pa.field("rule_id", pa.string(), nullable=False),
            pa.field("value", pa.string(), nullable=False),
            pa.field("start", pa.int32(), nullable=False),
            pa.field("end", pa.int32(), nullable=False),
            pa.field("text", pa.string(), nullable=False),
        ]
    )
    types = {
        "record_key": pa.string(),
        "source_row_index": pa.int64(),
        "source_dataset_id": pa.int64(),
        "source_content_hash": pa.string(),
        "year_value": pa.int16(),
        "job_title_clean": pa.string(),
        "job_industry_clean": pa.string(),
        "occupation_primary": pa.string(),
        "occupation_status": pa.string(),
        "occupation_method": pa.string(),
        "occupation_candidates": pa.list_(pa.string()),
        "occupation_source_candidates": pa.list_(pa.string()),
        "domains": pa.list_(pa.string()),
        "occupation_flags": pa.list_(pa.string()),
        "occupation_evidence": pa.list_(evidence),
        "location_places": pa.list_(pa.string()),
        "location_status": pa.string(),
        "location_group": pa.string(),
        "location_remote": pa.bool_(),
        "location_nationwide": pa.bool_(),
        "location_foreign": pa.list_(pa.string()),
        "location_flags": pa.list_(pa.string()),
        "location_evidence": pa.list_(evidence),
        "location_address_links": pa.list_(
            pa.struct(
                [
                    pa.field("rule_id", pa.string(), nullable=False),
                    pa.field("place", pa.string(), nullable=False),
                    *[
                        pa.field(name, pa.int32(), nullable=False)
                        for name in [
                            "partial_start",
                            "partial_end",
                            "complete_start",
                            "complete_end",
                        ]
                    ],
                ]
            )
        ),
        "family_record_count": pa.int64(),
        "scope_500": pa.bool_(),
        "scope_1000": pa.bool_(),
        "scope_reason": pa.string(),
        "enrichment_version": pa.string(),
        "taxonomy_version": pa.string(),
        "location_version": pa.string(),
    }
    optional = {"occupation_primary", "job_industry_clean"}
    return pa.schema(
        [pa.field(name, dtype, nullable=name in optional) for name, dtype in types.items()]
    )
