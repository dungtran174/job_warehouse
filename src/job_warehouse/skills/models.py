"""Stable skill concepts, exact spans and per-document extraction results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    code: str
    name: str
    group: str
    definition: str


@dataclass(frozen=True)
class Alias:
    skill_code: str
    text: str
    mode: str = "literal"


@dataclass(frozen=True)
class Evidence:
    skill_code: str
    start: int
    end: int
    text: str
    context_start: int
    context_end: int
    context: str
    rule_id: str
    logic: str = "single"
    group_id: str | None = None


@dataclass(frozen=True)
class Extraction:
    status: str
    skill_codes: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextOverride:
    text_hash: str
    skill_code: str
    evidence: str
    context: str
    decision: str


@dataclass(frozen=True)
class SkillPolicy:
    """Positive-pair semantics must be explicit, never silently chosen by a CLI."""

    version: str
    positive_contexts: tuple[str, ...]
    # Owner-approved finite certificate mapping; proficiency levels are not inferred.
    certificate_policy: str = "mapped_language"
    context_overrides: tuple[ContextOverride, ...] = ()

    def __post_init__(self) -> None:
        if not self.version or set(self.positive_contexts) not in (
            {"required"},
            {"required", "preferred"},
        ):
            raise ValueError("Choose required or required+preferred pair contexts explicitly")
        if self.certificate_policy not in {"evidence_only", "mapped_language"}:
            raise ValueError("Unknown certificate policy")
        if any(
            len(o.text_hash) != 64
            or o.context not in {"required", "preferred"}
            or not o.evidence
            or not o.decision
            for o in self.context_overrides
        ):
            raise ValueError("Invalid owner context override")
