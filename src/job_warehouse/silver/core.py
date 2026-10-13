"""One physical source row → one core record or a reasoned quarantine record."""

from dataclasses import asdict
from hashlib import sha256
from typing import Any

from job_warehouse.history.contract import YEARS
from job_warehouse.history.identity import HistoryRow, content_fingerprint, record_key
from job_warehouse.silver.categorical import education, job_type, position
from job_warehouse.silver.models import Claim, Experience, Inference
from job_warehouse.silver.requirements_attributes import extract_attributes
from job_warehouse.silver.text import normalize_content, normalize_text


def experience_fields(value: Experience, prefix: str = "experience") -> dict[str, Any]:
    result = {f"{prefix}_{key}": val for key, val in asdict(value).items()}
    result[f"{prefix}_min_years"] = value.years(value.min_months)
    result[f"{prefix}_max_years"] = value.years(value.max_months)
    result[f"{prefix}_years_rounded"] = any(
        rounded is not None and rounded * 12 != val
        for val, rounded in [(v, value.years(v)) for v in (value.min_months, value.max_months)]
    )
    return result


def claim_record(claim: Claim, text: str, digest: str, ordinal: int) -> dict[str, Any]:
    from job_warehouse.silver import EXTRACTOR_VERSION, MAPPING_VERSION

    if not (0 <= claim.context_start <= claim.start < claim.end <= claim.context_end <= len(text)):
        raise ValueError("Invalid requirement evidence offsets")
    return {
        "attribute": claim.attribute,
        "claim_ordinal": ordinal,
        "parsed_value": {
            "options": list(claim.options),
            "relation": claim.relation,
            "qualification_state": claim.qualification,
            "experience": asdict(claim.experience) if claim.experience else None,
        },
        "context": claim.context,
        "logic": claim.logic,
        "group_id": None,
        "experience_scope": claim.scope,
        "scope_text": claim.scope_text,
        "evidence_text": text[claim.start : claim.end],
        "start_offset": claim.start,
        "end_offset": claim.end,
        "context_text": text[claim.context_start : claim.context_end],
        "context_start": claim.context_start,
        "context_end": claim.context_end,
        "requirements_text_hash": digest,
        "rule_id": claim.rule_id,
        "rule_version": EXTRACTOR_VERSION,
        "dictionary_version": MAPPING_VERSION,
        "confidence_level": claim.confidence,
        "confidence_reasons": list(claim.reasons),
        "claim_status": claim.status,
    }


def _education_comparison(
    category: str | None, status: str, inferred: Inference
) -> tuple[str, list[str]]:
    if inferred.education_status in {"missing_requirements", "unusable_requirements"}:
        return "requirements_unavailable", []
    if category is None and status != "no_requirement":
        return "source_unavailable", []
    if inferred.education_status in {"complex", "ambiguous"}:
        return "complex_unresolved", []
    if inferred.education_relation is None:
        return "insufficient_evidence", []
    if status == "no_requirement" and inferred.education_relation == "no_requirement":
        return "consistent", []
    if category in inferred.education_options:
        return ("consistent" if len(inferred.education_options) == 1 else "compatible_detail"), []
    return "potential_conflict", ["source_label_and_required_degree_differ"]


def _experience_comparison(source: Experience, inferred: Inference) -> tuple[str, list[str]]:
    if inferred.experience_status in {"missing_requirements", "unusable_requirements"}:
        return "requirements_unavailable", []
    if source.status not in {"mapped", "no_requirement"}:
        return "source_unavailable", []
    if inferred.experience_status in {"complex", "ambiguous"}:
        return "complex_unresolved", []
    other = inferred.experience
    if other is None:
        return "insufficient_evidence", []
    keys = ("kind", "min_months", "max_months", "min_inclusive", "max_inclusive")
    if all(getattr(source, key) == getattr(other, key) for key in keys):
        return "consistent", []
    return "different_expression", ["different_source_and_requirement_expression; scope_may_differ"]


def normalize_row(
    row: HistoryRow, file_hash: str, row_index: int
) -> tuple[dict[str, Any], str | None]:
    from job_warehouse.silver.experience import parse_experience

    if (
        type(row["id"]) is not int
        or row["id"] <= 0
        or type(row["year"]) is not int
        or row["year"] not in YEARS
    ):
        raise ValueError("Source ID/year violates historical contract")
    identity = {
        "source_dataset_id": row["id"],
        "source_row_index": row_index,
        "record_key": record_key(file_hash, row_index),
        "source_content_hash": content_fingerprint(row),
    }

    def text_value(column: str) -> str | None:
        value = row[column]
        if value is not None and not isinstance(value, str):
            raise TypeError(f"Non-text source column: {column}")
        return value

    title = normalize_text(text_value("job_title"), short=True)
    reason = (
        "missing_title"
        if title.clean is None
        else "title_ambiguous_literal"
        if title.clean.casefold() == "không"
        else None
    )
    if reason:
        return {**dict(row), **identity, "quarantine_reason": reason}, reason
    company = normalize_text(text_value("company_name"), short=True)
    company_status = "placeholder" if company.clean == "." else company.status
    company_clean = None if company_status == "placeholder" else company.clean
    edu = education(text_value("education_level"))
    kind = job_type(text_value("job_type"))
    pos = position(text_value("job_position"))
    exp = parse_experience(text_value("experience_level"))
    flags = {f"job_title:{x}" for x in title.flags}
    flags.update(f"company_name:{x}" for x in company.flags)
    result: dict[str, Any] = {
        **dict(row),
        **identity,
        "job_title_clean": title.clean,
        "company_name_clean": company_clean,
        "company_match_key": company_clean.casefold() if company_clean else None,
        "company_mapping_status": company_status,
        "education_category": edu.category,
        "education_status": edu.status,
        "employment_types": list(kind.employment_types),
        "employment_type_group": kind.group,
        "work_arrangement": kind.work_arrangement,
        "shift_work": kind.shift_work,
        "job_type_status": kind.status,
        "job_type_unmapped": list(kind.unmapped),
        "position_label_clean": pos.label,
        "position_role_categories": list(pos.roles),
        "seniority_categories": list(pos.seniorities),
        "management_levels": list(pos.management),
        "position_status": pos.status,
        "year_value": row["year"],
        "year_status": "valid",
        **experience_fields(exp),
    }
    for column, status in [
        ("company_name", company_status),
        ("education_level", edu.status),
        ("job_type", kind.status),
        ("job_position", pos.status),
        ("experience_level", exp.status),
    ]:
        if status not in {"present", "mapped", "multiple", "no_requirement"}:
            flags.add(f"{column}:{status}")
    for column, status_name in [
        ("job_description", "description_status"),
        ("benefits", "benefits_status"),
        ("requirements", "requirements_status"),
    ]:
        value = normalize_content(text_value(column), requirements=column == "requirements")
        result[f"{column}_clean"] = value.clean
        result[status_name] = value.status
        result[f"{column}_decode_depth"] = value.decode_depth
        flags.update(f"{column}:{x}" for x in value.flags)
        if value.status != "present":
            flags.add(f"{column}:{value.status}")
    clean: str | None = result["requirements_clean"]
    digest = sha256(clean.encode()).hexdigest() if clean is not None else None
    result["requirements_text_hash"] = digest
    inferred = extract_attributes(clean, result["requirements_status"])
    result.update(
        education_inferred_options=list(inferred.education_options),
        education_inferred_relation=inferred.education_relation,
        education_inference_status=inferred.education_status,
        experience_inference_status=inferred.experience_status,
        requirements_attribute_groups=[],
    )
    inferred_exp = inferred.experience or Experience()
    fields = experience_fields(inferred_exp, "experience_inferred")
    # Absent summary remains null rather than an invented 'unknown' numeric requirement.
    if inferred.experience is None:
        fields = {key: None if not key.endswith("years_rounded") else False for key in fields}
    result.update(fields)
    for attribute in ["education", "experience"]:
        matching = [c for c in inferred.claims if c.attribute == attribute]
        result[f"{attribute}_inference_claims"] = (
            [claim_record(c, clean, digest, i) for i, c in enumerate(matching)]
            if clean is not None and digest is not None
            else []
        )
        status = getattr(inferred, f"{attribute}_status")
        if status in {"complex", "ambiguous"}:
            flags.add(f"{attribute}_inference:{status}")
    for attribute, comparison in [
        ("education", _education_comparison(edu.category, edu.status, inferred)),
        ("experience", _experience_comparison(exp, inferred)),
    ]:
        result[f"{attribute}_comparison_status"], result[f"{attribute}_comparison_reasons"] = (
            comparison
        )
        if comparison[0] == "potential_conflict":
            flags.add(f"{attribute}:potential_conflict")
    result["quality_flags"] = sorted(flags)
    result["processing_status"] = "ready_with_flags" if flags else "ready"
    return result, None
