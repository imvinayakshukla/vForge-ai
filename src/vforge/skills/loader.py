"""Load skills from ``skills/<name>/SKILL.md``.

A skill is reusable prompt material — domain knowledge, workflows, house
rules. The loader appends each requested skill's content to the agent's
system prompt, clearly delimited.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = "skills"
SKILL_FILENAME = "SKILL.md"


class SkillError(RuntimeError):
    """Raised when a configured skill cannot be loaded."""


def load_skills(app_dir: str | Path, names: list[str]) -> str:
    """Return the concatenated content of the named skills.

    Raises :class:`SkillError` if any skill directory or SKILL.md is missing —
    configuration errors surface at startup, not mid-conversation.
    """
    if not names:
        return ""
    app_dir = Path(app_dir)
    sections: list[str] = []
    for name in names:
        path = app_dir / SKILLS_DIR / name / SKILL_FILENAME
        if not path.is_file():
            raise SkillError(f"Skill '{name}' not found (expected {path})")
        content = path.read_text(encoding="utf-8").strip()
        sections.append(f"<skill name=\"{name}\">\n{content}\n</skill>")
        logger.debug("Loaded skill '%s' (%d chars)", name, len(content))
    return "\n\n".join(sections)


def apply_skills(system_prompt: str, skills_block: str) -> str:
    """Append the loaded skills to a system prompt."""
    if not skills_block:
        return system_prompt
    return f"{system_prompt}\n\n# Skills\n\n{skills_block}"
