"""Tests for the LLM service."""

from app.services.llm_service import GPT_5_SYSTEM_PROMPT, GPT_6_SYSTEM_PROMPT


def test_gpt6_prompt_drops_checklist_instruction() -> None:
    assert "checklist" in GPT_5_SYSTEM_PROMPT
    assert "checklist" not in GPT_6_SYSTEM_PROMPT
