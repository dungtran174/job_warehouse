"""Resolve explicitly approved industry rollups, without interpreting job text."""

from __future__ import annotations

from collections.abc import Mapping

INDUSTRY_ROLLUP_VERSION = "owner-industry-rollup-v1"


def resolve_industry_rollup(label: str, decisions: Mapping[str, str]) -> str:
    """Follow a selected child-parent chain to one final label; reject cycles."""
    current = label
    visited: set[str] = set()
    while current in decisions:
        if current in visited:
            raise ValueError(f"Cycle in industry rollup at {current!r}")
        visited.add(current)
        target = decisions[current]
        if not target.strip():
            raise ValueError(f"Empty parent label for {current!r}")
        current = target
    return current
