"""Skill loader tests."""

import pytest

from vforge.skills.loader import SkillError, apply_skills, load_skills


def test_loads_single_skill(app_dir):
    block = load_skills(app_dir, ["greeting"])
    assert 'name="greeting"' in block
    assert "Always greet politely." in block


def test_loads_multiple_skills(app_dir):
    extra = app_dir / "skills" / "second"
    extra.mkdir(parents=True)
    (extra / "SKILL.md").write_text("Second skill content.")
    block = load_skills(app_dir, ["greeting", "second"])
    assert "Always greet politely." in block
    assert "Second skill content." in block


def test_missing_skill_raises(app_dir):
    with pytest.raises(SkillError, match="ghost"):
        load_skills(app_dir, ["ghost"])


def test_no_skills_is_noop(app_dir):
    assert load_skills(app_dir, []) == ""
    assert apply_skills("prompt", "") == "prompt"


def test_apply_appends_section():
    result = apply_skills("Base prompt.", "<skill>x</skill>")
    assert result.startswith("Base prompt.")
    assert "# Skills" in result
