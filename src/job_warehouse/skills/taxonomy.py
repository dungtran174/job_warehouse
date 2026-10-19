"""Load literal aliases; taxonomy definitions do not assign skills to occupations."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from job_warehouse.skills.models import Alias, Skill

MAPPINGS = Path(__file__).with_name("mappings")


@dataclass(frozen=True)
class Taxonomy:
    skills: dict[str, Skill]
    aliases: tuple[Alias, ...]

    def __post_init__(self) -> None:
        if not self.skills:
            raise ValueError("Empty taxonomy")
        seen: dict[str, str] = {}
        used: set[str] = set()
        for code, skill in self.skills.items():
            if (
                code != skill.code
                or not re.fullmatch(r"[a-z][a-z0-9_]*", code)
                or not skill.name.strip()
                or not skill.definition.strip()
                or skill.group not in {"tool", "technology", "domain", "language"}
            ):
                raise ValueError("Invalid skill concept or group")
        for alias in self.aliases:
            key = alias.text.casefold()
            if (
                alias.skill_code not in self.skills
                or not key.strip()
                or alias.text != alias.text.strip()
            ):
                raise ValueError("Invalid alias or missing canonical skill")
            if key in seen:
                raise ValueError("Duplicate or conflicting alias")
            if alias.mode not in {"literal", "contextual", "certificate", "shared_language"}:
                raise ValueError("Unknown alias mode")
            if alias.mode == "certificate" and self.skills[alias.skill_code].group != "language":
                raise ValueError("Certificate mapping must target a language")
            if (
                alias.mode == "shared_language"
                and self.skills[alias.skill_code].group != "language"
            ):
                raise ValueError("Shared language names must target a language")
            if len(key) <= 2 and key.isalpha() and alias.mode != "contextual":
                raise ValueError("Short aliases need explicit contextual matching")
            seen[key] = alias.skill_code
            used.add(alias.skill_code)
        if used != set(self.skills):
            raise ValueError("Every skill needs an alias")


def load_taxonomy(directory: Path = MAPPINGS) -> Taxonomy:
    skills: dict[str, Skill] = {}
    with (directory / "taxonomy.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            code = row["skill_code"]
            if code in skills:
                raise ValueError("Duplicate canonical skill code")
            skills[code] = Skill(code, row["skill_name"], row["skill_group"], row["definition"])
    with (directory / "aliases.csv").open(encoding="utf-8", newline="") as stream:
        aliases = tuple(
            Alias(row["skill_code"], row["alias"], row["mode"]) for row in csv.DictReader(stream)
        )
    return Taxonomy(skills, aliases)
