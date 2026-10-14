"""Read and validate packaged, versioned CSV resources (also in installed wheels)."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from importlib.resources import files


def read_csv(name: str) -> list[dict[str, str]]:
    resource = files("job_warehouse.silver.enrichment").joinpath("mappings", name)
    return list(csv.DictReader(io.StringIO(resource.read_text(encoding="utf-8"))))


def configuration_hashes() -> dict[str, str]:
    root = files("job_warehouse.silver.enrichment")
    resources = [(p.name, p) for p in root.iterdir() if p.name.endswith(".py")]
    resources.extend((f"mappings/{p.name}", p) for p in root.joinpath("mappings").iterdir())
    return {
        name: hashlib.sha256(resource.read_bytes()).hexdigest()
        for name, resource in sorted(resources, key=lambda item: item[0])
        if resource.is_file()
    }


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    value: str
    pattern: re.Pattern[str]
    exclude: re.Pattern[str] | None


def load_rules(name: str, values: set[str]) -> tuple[Rule, ...]:
    rules = []
    seen: set[str] = set()
    for row in read_csv(name):
        if not row["rule_id"] or row["rule_id"] in seen:
            raise ValueError(f"Duplicate or empty rule ID: {name}")
        seen.add(row["rule_id"])
        if row["value"] not in values:
            raise ValueError(f"Unknown rule value: {name}: {row['value']}")
        pattern = re.compile(row["pattern"], re.IGNORECASE)
        if pattern.search(""):
            raise ValueError(f"Empty-match rule: {row['rule_id']}")
        rules.append(
            Rule(
                row["rule_id"],
                row["value"],
                pattern,
                re.compile(row["exclude"], re.IGNORECASE) if row["exclude"] else None,
            )
        )
    return tuple(rules)
