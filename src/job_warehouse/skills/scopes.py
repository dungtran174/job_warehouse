"""Select validated source labels without changing the frozen extraction rules."""

from job_warehouse.skills.batches import batch_scope


def processing_scope(name: str, industries: tuple[str, ...] | None = None) -> tuple[str, ...]:
    approved = batch_scope(name)
    if industries is None:
        return approved
    if (
        not industries
        or len(set(industries)) != len(industries)
        or not set(industries) <= set(approved)
    ):
        raise ValueError("Choose a nonempty, unique subset of the approved batch labels")
    return tuple(label for label in approved if label in industries)
