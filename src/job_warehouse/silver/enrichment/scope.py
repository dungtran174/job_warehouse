"""Post-mapping analytical scope; never delete core rows or count labels as jobs."""

from collections.abc import Mapping


def scope_reason(primary: str | None, counts: Mapping[str, int], threshold: int = 500) -> str:
    if threshold < 1:
        raise ValueError("Scope threshold must be positive")
    if primary is None:
        return "occupation_unresolved"
    if primary not in counts or counts[primary] < 0:
        raise ValueError("Assigned family must have a nonnegative population count")
    return "eligible" if counts[primary] >= threshold else "below_family_threshold"
