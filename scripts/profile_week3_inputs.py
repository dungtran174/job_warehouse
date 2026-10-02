"""Read-only, offline coverage profiling. Writes reports only, never raw/checkpoints."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from selectolax.parser import HTMLParser

from job_crawler.parsers.careerviet_detail import _job_posting, _labeled_value, _section

DEFAULTS = {
    "careerlink": "data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20",
    "careerviet": "data/raw/careerviet/snapshot_date=2026-09-22/batch_id=20260922T165843Z-f6b389a4",
}


def json_type(value):
    return {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }[type(value)]


def missing_kind(row, field):
    if field not in row:
        return "absent"
    value = row[field]
    if value is None:
        return "null"
    if isinstance(value, str) and not value.strip():
        return "blank_string"
    if isinstance(value, list) and not value:
        return "empty_array"
    return "present"


def salary_shape(value):
    if value is None:
        return "null"
    if value in ("Thương lượng", "Cạnh tranh"):
        return value
    if re.fullmatch(r"\d+(?:\.\d+)? triệu - \d+(?:\.\d+)? triệu", value):
        return "range_million_decimal" if "." in value else "range_million_integer"
    if re.fullmatch(r"\d+ - \d+ (VND|USD) MONTH", value):
        return "range_" + value.split()[-2] + "_MONTH"
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return "bare_number_ambiguous_bound"
    return "other"


def distribution(values):
    counts = Counter(json.dumps(v, ensure_ascii=False, sort_keys=True) for v in values)
    return [{"value": json.loads(v), "count": n} for v, n in counts.most_common()]


def field_profile(rows):
    result = {}
    for field in sorted(set().union(*(r.keys() for r in rows))):
        missing = Counter(missing_kind(r, field) for r in rows)
        values = [r[field] for r in rows if field in r]
        missing_count = len(rows) - missing["present"]
        result[field] = {
            "types": dict(Counter(json_type(v) for v in values)),
            "missing": dict(missing),
            "missing_count": missing_count,
            "missing_pct": round(100 * missing_count / len(rows), 2),
            "distinct_json_values": len({json.dumps(v, sort_keys=True) for v in values}),
            "array_element_types": dict(
                Counter(json_type(x) for v in values if isinstance(v, list) for x in v)
            ),
        }
    return result


def clean(value):
    return re.sub(r"\s+", " ", value).strip()


def profile(root):
    raw_path = root / "jobs.jsonl"
    rows = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
    source = rows[0]["source_name"]
    html_rows = []
    for row in rows:
        if not row.get("raw_html_path"):
            html_rows.append(
                {
                    "id": row["source_job_id"],
                    "html_path": None,
                    "sections": {
                        field: {
                            "characters": len(row[field]),
                            "blocks": None,
                            "full_dom_match": None,
                            "full_source_match": None,
                            "value_source": "unavailable",
                            "tag_counts": {},
                            "has_dash_bullet": None,
                            "newlines_in_jsonl": row[field].count("\n"),
                        }
                        for field in ("job_description", "candidate_requirements")
                    },
                }
            )
            continue
        path = root / row["raw_html_path"]
        tree = HTMLParser(gzip.decompress(path.read_bytes()).decode())
        posting = _job_posting(tree)
        item = {"id": row["source_job_id"], "html_path": str(path), "sections": {}}
        for field, section_name in [
            ("job_description", "job_description"),
            ("candidate_requirements", "candidate_requirements"),
        ]:
            if source == "careerlink":
                prefix = "description" if field == "job_description" else "skills"
                nodes = tree.css(f"#section-job-{prefix} .rich-text-content")
            else:
                section = _section(tree, section_name)
                nodes = (
                    [section.css_first(".content_fck, .detail-content") or section]
                    if section
                    else []
                )
            text = clean(" ".join(n.text(separator=" ", strip=True) for n in nodes))
            value_source = "dom"
            if source == "careerviet" and section is not None:
                heading = section.css_first(".detail-title, h2, h3, h4")
                if not section.css_first(".content_fck, .detail-content") and heading:
                    label = clean(heading.text(separator=" ", strip=True))
                    if text.startswith(label):
                        text = text[len(label) :].strip()
            if not nodes:
                key = "description" if field == "job_description" else "qualifications"
                payload = posting.get(key)
                if isinstance(payload, str):
                    text = clean(HTMLParser(payload).text(separator=" ", strip=True))
                    value_source = "jsonld"
                else:
                    value_source = "missing"
            tags = Counter(
                n.tag for block in nodes for n in block.css("p,ul,ol,li,br,table,strong,b,em")
            )
            item["sections"][field] = {
                "characters": len(row[field]),
                "blocks": len(nodes),
                "full_dom_match": value_source == "dom" and text == row[field],
                "full_source_match": text == row[field],
                "value_source": value_source,
                "tag_counts": dict(tags),
                "has_dash_bullet": bool(re.search(r"(?:^|\s)[-*•]\s", text)),
                "newlines_in_jsonl": row[field].count("\n"),
            }
        if source == "careerlink":
            summary = {}
            for node in tree.css("#section-job-summary .job-summary-item"):
                label = node.css_first(".summary-label")
                value = node.css_first(".font-weight-bolder")
                if label and value:
                    summary[clean(label.text())] = clean(value.text(separator=" ", strip=True))
            company = tree.css_first(".job-detail-header .org-name a[href]")
            item.update(
                summary=summary,
                location_blocks=[
                    clean(n.text(separator=" ", strip=True)) for n in tree.css("#job-location")
                ],
                location_links=[
                    clean(n.text(separator=" ", strip=True)) for n in tree.css("#job-location a")
                ],
                office_present=bool(tree.css("#job-offices")),
                benefits_present=bool(tree.css("#section-job-benefits .job-benefit-item")),
                company_url=company.attributes.get("href") if company else None,
                expiry_present=bool(tree.css("#job-date .day-expired")),
                company_size_values=[
                    clean(n.text())
                    for n in tree.css("#section-about-company .list-company-info span")
                    if "nhân viên" in n.text()
                ],
            )
        else:
            item["visible_salary"] = _labeled_value(tree, "Lương")
        item["jsonld"] = {
            k: posting.get(k)
            for k in [
                "datePosted",
                "validThrough",
                "baseSalary",
                "jobLocation",
                "employmentType",
                "industry",
                "workHours",
                "totalJobOpenings",
            ]
        }
        html_rows.append(item)
    stats = {}
    for field in ["job_description", "candidate_requirements"]:
        lengths = [len(r[field]) for r in rows]
        stats[field] = {
            "min": min(lengths),
            "median": median(lengths),
            "max": max(lengths),
            "full_dom_match_count": sum(
                h["sections"][field]["full_dom_match"] is True for h in html_rows
            ),
            "full_source_match_count": sum(
                h["sections"][field]["full_source_match"] is True for h in html_rows
            ),
            "value_sources": dict(Counter(h["sections"][field]["value_source"] for h in html_rows)),
            "records_by_tag": dict(
                Counter(tag for h in html_rows for tag in h["sections"][field]["tag_counts"])
            ),
            "dash_bullet_records": sum(
                h["sections"][field]["has_dash_bullet"] is True for h in html_rows
            ),
            "with_newline": sum(h["sections"][field]["newlines_in_jsonl"] > 0 for h in html_rows),
        }
    posting_dates = []
    future_ids = []
    for row in rows:
        value = row["posted_at_raw"]
        posted = (
            datetime.strptime(value, "%d-%m-%Y")
            if source == "careerlink"
            else datetime.fromisoformat(value.replace("Z", "+00:00"))
        )
        posting_dates.append(posted.date().isoformat())
        crawled = datetime.fromisoformat(row["crawled_at"].replace("Z", "+00:00"))
        if source == "careerlink":
            future = posted.date() > crawled.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        else:
            future = posted > crawled
        if future:
            future_ids.append(row["source_job_id"])
    return {
        "source": source,
        "path": str(root),
        "records": len(rows),
        "html_records_available": sum(h["html_path"] is not None for h in html_rows),
        "html_records_unavailable": sum(h["html_path"] is None for h in html_rows),
        "jobs_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "unique_ids": len({r["source_job_id"] for r in rows}),
        "fields": field_profile(rows),
        "distinct_company_names": len({r["company_name"] for r in rows}),
        "top_companies": distribution(r["company_name"] for r in rows)[:10],
        "distributions": {
            f: distribution(r[f] for r in rows)
            for f in [
                "salary_raw",
                "location_raw",
                "posted_at_raw",
                "posted_date_precision",
                "snapshot_date",
                "job_type",
                "education_level",
                "job_level",
                "experience_raw",
                "working_time",
            ]
        },
        "salary_shapes": dict(Counter(salary_shape(r["salary_raw"]) for r in rows)),
        "posting_date_range": [min(posting_dates), max(posting_dates)],
        "posted_after_crawled_ids": future_ids,
        "crawled_local_dates": dict(
            Counter(
                datetime.fromisoformat(r["crawled_at"].replace("Z", "+00:00"))
                .astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
                .date()
                .isoformat()
                for r in rows
            )
        ),
        "snapshot_vs_crawled_date_mismatch": sum(
            r["snapshot_date"]
            != datetime.fromisoformat(r["crawled_at"].replace("Z", "+00:00"))
            .astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
            .date()
            .isoformat()
            for r in rows
        ),
        "text_statistics": stats,
        "html_evidence": html_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    profiles = {name: profile(Path(path)) for name, path in DEFAULTS.items()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "profiles.json").write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2)
    )
    with (args.output_dir / "field_profile.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "source",
                "field",
                "types",
                "absent",
                "null",
                "blank_string",
                "empty_array",
                "missing_count",
                "missing_pct",
                "distinct_values",
            ]
        )
        for name, data in profiles.items():
            for field, p in data["fields"].items():
                writer.writerow(
                    [
                        name,
                        field,
                        json.dumps(p["types"]),
                        *(
                            p["missing"].get(k, 0)
                            for k in ["absent", "null", "blank_string", "empty_array"]
                        ),
                        p["missing_count"],
                        p["missing_pct"],
                        p["distinct_json_values"],
                    ]
                )
    for data in profiles.values():
        print(
            json.dumps(
                {
                    k: v
                    for k, v in data.items()
                    if k not in {"fields", "distributions", "html_evidence"}
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
