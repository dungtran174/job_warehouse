"""Explicit Arrow schemas including typed nested claims, even for empty outputs."""

import pyarrow as pa

from job_warehouse.history.contract import COLUMNS

DECIMAL = pa.decimal128(18, 6)
EXPERIENCE_TYPES = {
    "min_months": DECIMAL,
    "max_months": DECIMAL,
    "min_inclusive": pa.bool_(),
    "max_inclusive": pa.bool_(),
    "kind": pa.string(),
    "group": pa.string(),
    "status": pa.string(),
    "source_unit": pa.string(),
    "source_min": pa.string(),
    "source_max": pa.string(),
}
CLAIM = pa.struct(
    [
        ("attribute", pa.string()),
        ("claim_ordinal", pa.int32()),
        (
            "parsed_value",
            pa.struct(
                [
                    ("options", pa.list_(pa.string())),
                    ("relation", pa.string()),
                    ("qualification_state", pa.string()),
                    ("experience", pa.struct(list(EXPERIENCE_TYPES.items()))),
                ]
            ),
        ),
        *[
            (x, pa.string())
            for x in [
                "context",
                "logic",
                "group_id",
                "experience_scope",
                "scope_text",
                "evidence_text",
                "context_text",
                "requirements_text_hash",
                "rule_id",
                "rule_version",
                "dictionary_version",
                "confidence_level",
                "claim_status",
            ]
        ],
        *[(x, pa.int32()) for x in ["start_offset", "end_offset", "context_start", "context_end"]],
        ("confidence_reasons", pa.list_(pa.string())),
    ]
)
IDENTITY = [
    ("source_dataset_id", pa.int64()),
    ("source_row_index", pa.int64()),
    ("record_key", pa.string()),
    ("source_content_hash", pa.string()),
]
RAW = [(c, pa.int64() if c in {"id", "year"} else pa.string()) for c in COLUMNS]


def quarantine_schema() -> pa.Schema:
    return pa.schema([*RAW, *IDENTITY, ("quarantine_reason", pa.string())])


def core_schema() -> pa.Schema:
    text = [
        "job_title_clean",
        "company_name_clean",
        "company_match_key",
        "company_mapping_status",
        "education_category",
        "education_status",
        "employment_type_group",
        "work_arrangement",
        "job_type_status",
        "position_label_clean",
        "position_status",
        "year_status",
        "job_description_clean",
        "benefits_clean",
        "requirements_clean",
        "description_status",
        "benefits_status",
        "requirements_status",
        "requirements_text_hash",
        "education_inferred_relation",
        "education_inference_status",
        "experience_inference_status",
        "education_comparison_status",
        "experience_comparison_status",
        "processing_status",
    ]
    arrays = [
        "employment_types",
        "job_type_unmapped",
        "position_role_categories",
        "seniority_categories",
        "management_levels",
        "education_inferred_options",
        "education_comparison_reasons",
        "experience_comparison_reasons",
        "quality_flags",
    ]
    fields = [
        *RAW,
        *IDENTITY,
        *[(x, pa.string()) for x in text],
        *[(x, pa.list_(pa.string())) for x in arrays],
        ("shift_work", pa.bool_()),
        ("year_value", pa.int16()),
        *[
            (f"{x}_decode_depth", pa.int16())
            for x in ["job_description", "benefits", "requirements"]
        ],
        ("education_inference_claims", pa.list_(CLAIM)),
        ("experience_inference_claims", pa.list_(CLAIM)),
        (
            "requirements_attribute_groups",
            pa.list_(pa.struct([("group_id", pa.string()), ("logic", pa.string())])),
        ),
    ]
    for prefix in ["experience", "experience_inferred"]:
        fields.extend((f"{prefix}_{name}", dtype) for name, dtype in EXPERIENCE_TYPES.items())
        fields.extend(
            [
                (f"{prefix}_min_years", DECIMAL),
                (f"{prefix}_max_years", DECIMAL),
                (f"{prefix}_years_rounded", pa.bool_()),
            ]
        )
    return pa.schema(fields)
