"""Expose the built-in API path/field map used by the dashboard modules."""

from __future__ import annotations

from api_config import API_ANSWERS


def load_answers() -> dict[str, str]:
    return dict(API_ANSWERS)


def get_answer(var: str, default: str = "") -> str:
    return API_ANSWERS.get(var, default)


def answers_for_variables(variables: list[str]) -> dict[str, str]:
    return {var: API_ANSWERS.get(var, "") for var in variables}
