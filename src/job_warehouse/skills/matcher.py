"""Literal, longest-first matching with source offsets and auditable pair semantics."""

import re
from collections import deque
from dataclasses import replace

from job_warehouse.skills.context import (
    ABILITY,
    MARKETING_CONTEXT,
    NEGATED,
    OR,
    PREFERRED,
    SHARED_LANGUAGE_PREFIX,
    classify_context,
    clauses,
)
from job_warehouse.skills.input import PLACEHOLDERS
from job_warehouse.skills.models import Alias, Evidence, Extraction, SkillPolicy
from job_warehouse.skills.profile import text_hash
from job_warehouse.skills.taxonomy import Taxonomy


def alias_pattern(alias: str) -> str:
    # Do not silently strip C++/C#/.NET symbols; do not match SQL in PostgreSQL.
    # A plain C alias must not match C++ or C#, even in a custom taxonomy.
    left = r"(?<![\w.])" if alias.startswith(".") else r"(?<!\w)"
    return left + re.escape(alias) + r"(?![\w+#])"


class SkillMatcher:
    def __init__(self, taxonomy: Taxonomy, policy: SkillPolicy) -> None:
        self.taxonomy, self.policy = taxonomy, policy
        self._aliases = sorted(taxonomy.aliases, key=lambda a: (-len(a.text), a.text.casefold()))
        # Aho-Corasick trie: scan text once instead of trying every alias at each
        # position. A separate original-offset map handles Unicode expansions.
        self._edges: list[dict[str, int]] = [{}]
        self._fail = [0]
        self._outputs: list[list[int]] = [[]]
        self._lengths = [len(alias.text.casefold()) for alias in self._aliases]
        for index, alias in enumerate(self._aliases):
            state = 0
            for char in alias.text.casefold():
                if char not in self._edges[state]:
                    self._edges[state][char] = len(self._edges)
                    self._edges.append({})
                    self._fail.append(0)
                    self._outputs.append([])
                state = self._edges[state][char]
            self._outputs[state].append(index)
        queue = deque(self._edges[0].values())
        while queue:
            parent = queue.popleft()
            for char, child in self._edges[parent].items():
                queue.append(child)
                failure = self._fail[parent]
                while failure and char not in self._edges[failure]:
                    failure = self._fail[failure]
                self._fail[child] = self._edges[failure].get(char, 0)
                self._outputs[child].extend(self._outputs[self._fail[child]])

    @staticmethod
    def _word(char: str) -> bool:
        return char.isalnum() or char == "_"

    def _boundary_ok(self, text: str, start: int, end: int, alias: Alias) -> bool:
        if start and (
            self._word(text[start - 1]) or (alias.text.startswith(".") and text[start - 1] == ".")
        ):
            return False
        return not (end < len(text) and (self._word(text[end]) or text[end] in "+#"))

    @staticmethod
    def _alias_context_ok(text: str, start: int, end: int, alias: Alias) -> bool:
        if alias.mode == "contextual" and alias.text.casefold() in {"ai", "ps", "pr"}:
            # AI may mean artificial intelligence; PR may mean public relations.
            # Only accept product abbreviations in explicit creative-software context.
            before = re.split(r"[;\n•●]", text[max(0, start - 180) : start])[-1]
            after = re.split(r"[;\n•●]", text[end : end + 180])[0]
            local = before + text[start:end] + after
            if alias.text.casefold() == "ai" and re.match(
                r"\s+(?:hỗ trợ|tạo sinh|generative|assist)", after, re.I
            ):
                return False
            if alias.text.casefold() == "pr" and re.search(
                r"(?:bài|viết|quan hệ|chiến dịch)\s*$", before, re.I
            ):
                return False
            return bool(
                re.search(r"phần mềm|công cụ|software|tools?", local, re.I)
                and re.search(
                    r"thiết kế|đồ họa|chỉnh sửa|graphic|design|\bPTS\b",
                    local,
                    re.I,
                )
                and (
                    alias.text.casefold() != "pr"
                    or re.search(r"video|CapCut|Premiere|hậu kỳ|editing", local, re.I)
                )
            )
        if alias.mode == "shared_language":
            return bool(SHARED_LANGUAGE_PREFIX.search(text[max(0, start - 140) : start]))
        if alias.mode == "contextual" and alias.text.casefold() == "rest":
            return bool(
                re.search(
                    r"API|integrations?|tích hợp|web\s*services?|HTTP|SOAP",
                    text[max(0, start - 100) : end + 150],
                    re.I,
                )
            )
        if alias.mode == "contextual" and alias.skill_code in {
            "digital_marketing",
            "content_marketing",
            "social_media",
        }:
            if not MARKETING_CONTEXT.search(text):
                return False
            if alias.text.casefold() == "tiktok/reels" and not re.search(
                r"kinh nghiệm|sản xuất|phát triển|quản trị|tương tác|đăng bài|engagement",
                text[max(0, start - 160) : end + 100],
                re.I,
            ):
                return False
            if alias.skill_code == "digital_marketing" and re.match(
                r"\s+(?:products?|devices?|transformation|signature|camera|circuits?|electronics?)\b",
                text[end:],
                re.I,
            ):
                return False
        if alias.mode == "contextual" and alias.skill_code in {
            "facebook_ads",
            "google_ads",
            "tiktok_ads",
        }:
            if alias.skill_code == "google_ads" and re.match(
                r"\s+(?:Analytics|Search|Console|Cloud|Sheets|Drive|Tag|Workspace)\b",
                text[end:],
                re.I,
            ):
                return False
            before = re.split(
                r"[.;\n•●]|\s+[-–—]\s+|(?=Hiểu biết\b|Có khả năng\b|Kỹ năng\b)",
                text[max(0, start - 300) : start],
            )[-1]
            # A shared advertising head can govern a platform list; do not carry
            # it into a later capability clause about general social networks.
            if re.search(r"fanpage", before, re.I) and not re.search(
                r"\bads?\b|paid|chạy quảng cáo", before, re.I
            ):
                return False
            return bool(
                re.search(r"quảng cáo|\bads?\b|paid channels?|advertising", before, re.I)
                or re.match(r"\s*(?:ads?\b|advertising)", text[end:], re.I)
            )
        if alias.skill_code == "social_media" and alias.mode == "contextual":
            local = re.split(r"[.;\n•●]", text[max(0, start - 140) : start])[-1]
            if re.search(r"edit video|video editing|video formats?", local, re.I) and not re.search(
                r"analytics|phân tích|quản lý|quản trị|vận hành|engagement", local, re.I
            ):
                return False
        if (
            alias.mode == "contextual"
            and alias.text.casefold() == "office"
            and re.search(
                r"\b(?:front|back|head|regional|main|in)[ -]*$",
                text[max(0, start - 30) : start],
                re.I,
            )
        ):
            return False
        return not (
            alias.skill_code == "fast_accounting"
            and alias.text.casefold() == "fast"
            and re.match(
                r"[-\s]*(?:(?:self[-\s]*)?learn\w*|evolving|paced|growing|moving)\b",
                text[end:],
                re.I,
            )
        )

    def _candidates(self, text: str) -> list[tuple[int, int, Alias]]:
        pieces, offsets = [], []
        for index, char in enumerate(text):
            folded = char.casefold()
            pieces.append(folded)
            offsets.extend([index] * len(folded))
        folded_text = "".join(pieces)
        matches: list[tuple[int, int, int]] = []
        state = 0
        for index, char in enumerate(folded_text):
            while state and char not in self._edges[state]:
                state = self._fail[state]
            state = self._edges[state].get(char, 0)
            for alias_index in self._outputs[state]:
                folded_start = index - self._lengths[alias_index] + 1
                if (folded_start and offsets[folded_start - 1] == offsets[folded_start]) or (
                    index + 1 < len(offsets) and offsets[index + 1] == offsets[index]
                ):
                    continue  # Never take half of a casefold expansion.
                start, end = offsets[folded_start], offsets[index] + 1
                alias = self._aliases[alias_index]
                if self._boundary_ok(text, start, end, alias) and self._alias_context_ok(
                    text, start, end, alias
                ):
                    matches.append((start, end, alias_index))
        result: list[tuple[int, int, Alias]] = []
        implicit_parents = {
            "sql_server": {"sql"},
            "react_native": {"react"},
            "spring_boot": {"spring"},
            "pyspark": {"spark"},
        }
        for start, end, alias_index in sorted(matches, key=lambda m: (m[0], -(m[1] - m[0]), m[2])):
            alias = self._aliases[alias_index]
            overlapping = [a for s, e, a in result if s < end and start < e]
            if any(
                a.skill_code == alias.skill_code
                or alias.skill_code in implicit_parents.get(a.skill_code, set())
                for a in overlapping
            ):
                continue
            # Distinct explicit concepts may share words: 'viết SEO' names both
            # content production and SEO. Product names still suppress implicit parents.
            result.append((start, end, alias))
        return result

    def _segments(self, text: str, spans: list[tuple[int, int]]) -> list[tuple[int, int, str]]:
        """Default segmentation stays unchanged for the accepted older profiles."""
        return clauses(text, spans)

    def extract(self, text: str | None) -> Extraction:
        if text is None:
            return Extraction("missing_requirements")
        if text.strip().casefold() in PLACEHOLDERS:
            return Extraction("unusable_requirements")
        candidates = self._candidates(text)
        hashed = text_hash(text) if self.policy.context_overrides else None
        segments = self._segments(text, [(s, e) for s, e, _ in candidates])
        evidence = []
        for start, end, alias in candidates:
            left, right, section = next(
                segment for segment in segments if segment[0] <= start and end <= segment[1]
            )
            local_left, local_right = left, right
            following = [s for s, _, _ in candidates if end <= s < right]
            if following:
                local_right = min(following)
            previous = [e for _, e, _ in candidates if left <= e <= start]
            if previous:
                gap = text[max(previous) : start]
                if "," in gap and (NEGATED.search(gap) or PREFERRED.search(gap)):
                    local_left = max(previous) + gap.rfind(",") + 1
            skill = self.taxonomy.skills[alias.skill_code]
            context, reason = classify_context(
                text,
                start,
                end,
                local_left,
                local_right,
                section,
                language=skill.group == "language",
                certificate=alias.mode == "certificate",
            )
            local = text[left:right]
            # 'Fast learner / fast-evolving' is an ordinary English adjective,
            # not an unresolved claim about FAST accounting software.
            if (
                alias.skill_code == "fast_accounting"
                and alias.text.casefold() == "fast"
                and re.match(
                    r"[-\s]*(?:evolving|learner|learning|paced|growing)\b", text[end:], re.I
                )
            ):
                context, reason = "mentioned", "ordinary_word_not_product"
            if (
                alias.mode == "contextual"
                and alias.skill_code
                not in {
                    "content_marketing",
                    "digital_marketing",
                    "social_media",
                    "spark",
                    "fast_accounting",
                    "facebook_ads",
                    "tiktok_ads",
                    "rest_api",
                }
                and not (
                    ABILITY.search(local)
                    or re.search(r"Excel|PowerPoint|Microsoft|tin học|vi tính", local, re.I)
                )
                and context in self.policy.positive_contexts
            ):
                context, reason = "ambiguous", "short_or_ambiguous_alias"
            if (
                alias.mode == "contextual"
                and alias.skill_code in {"fast_accounting", "spark"}
                and context in self.policy.positive_contexts
            ):
                required_context = (
                    r"phần mềm|kế toán|accounting|MISA|BRAVO"
                    if alias.skill_code == "fast_accounting"
                    else r"big\s*data|data|dữ liệu|ETL|Hadoop|Scala|Apache"
                )
                if not re.search(required_context, local, re.I):
                    context, reason = "ambiguous", "product_context_unclear"
            if (
                alias.skill_code == "github"
                and re.search(r"CV|portfolio|gửi|đính kèm|profile|link", local, re.I)
                and not ABILITY.search(local)
            ):
                context, reason = "mentioned", "portfolio_not_tool_ability"
            if alias.skill_code == "github" and re.match(r"\s+Actions\b", text[end:], re.I):
                context, reason = "mentioned", "specific_product_not_implicit_parent"
            if alias.mode == "certificate":
                reason = f"certificate_to_language:{alias.text}:{reason}"
                if context == "negated":
                    context, reason = "mentioned", f"certificate_not_required:{alias.text}"
                if self.policy.certificate_policy == "evidence_only":
                    context = "mentioned"
            if alias.mode == "shared_language":
                reason = f"shared_language_name:{reason}"
            for override in self.policy.context_overrides:
                if hashed == override.text_hash and alias.skill_code == override.skill_code:
                    if override.evidence not in text or not (
                        text.find(override.evidence) <= start
                        and end <= text.find(override.evidence) + len(override.evidence)
                    ):
                        raise ValueError("Owner context override evidence mismatch")
                    context, reason = override.context, f"owner_context:{override.decision}"
            minimum = re.search(
                r"(?:ít nhất|at least)\s+(\d+|hai|ba)\s+(?:ngôn ngữ|công cụ|of)", local, re.I
            )
            logic = (
                f"minimum_subset:{minimum[1]}"
                if minimum
                else "any_of"
                if OR.search(local)
                else "listed_together_unspecified"
                if "/" in local or alias.mode == "shared_language"
                else "single"
            )
            evidence.append(
                Evidence(
                    alias.skill_code,
                    start,
                    end,
                    text[start:end],
                    left,
                    right,
                    context,
                    reason,
                    logic,
                    f"{left}:{right}" if logic != "single" else None,
                )
            )
        # Positive/negative evidence for the same concept requires review.
        conflicts = {
            code
            for code in {e.skill_code for e in evidence}
            if any(
                e.skill_code == code and e.context in self.policy.positive_contexts
                for e in evidence
            )
            and any(e.skill_code == code and e.context == "negated" for e in evidence)
        }
        evidence = [
            replace(e, context="ambiguous", rule_id="conflicting_assertions")
            if e.skill_code in conflicts
            else e
            for e in evidence
        ]
        reasons = tuple(sorted({e.rule_id for e in evidence if e.context == "ambiguous"}))
        if reasons:
            return Extraction("needs_review", evidence=tuple(evidence), reasons=reasons)
        codes = tuple(
            sorted({e.skill_code for e in evidence if e.context in self.policy.positive_contexts})
        )
        return Extraction(
            "processed_match" if codes else "processed_no_match", codes, tuple(evidence)
        )
