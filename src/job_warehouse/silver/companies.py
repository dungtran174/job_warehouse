"""Choose a source spelling for names equal after text cleanup and casefold."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping

from job_warehouse.silver.text import normalize_text

COMPANY_NAME_VERSION = "company-source-spelling-v1"


def company_spelling(value: str | None) -> str | None:
    clean = normalize_text(value, short=True).clean
    return None if clean == "." else clean


def preferred_company_names(values: Iterable[str | None]) -> dict[str, str]:
    counts: Counter[str] = Counter()
    for value in values:
        clean = company_spelling(value)
        if clean is not None:
            counts[clean] += 1
    groups: dict[str, list[str]] = defaultdict(list)
    for name in counts:
        groups[name.casefold()].append(name)
    return {
        key: min(names, key=lambda name: (-counts[name], name)) for key, names in groups.items()
    }


def canonical_company_name(clean: str, representatives: Mapping[str, str]) -> str:
    key = clean.casefold()
    if key not in representatives:
        raise ValueError("Company name absent from the verified source-name catalog")
    chosen = representatives[key]
    if chosen.casefold() != key:
        raise ValueError("Company representative changes more than letter case")
    return chosen
