"""Inject persisted lab answers onto module objects at request time."""

from __future__ import annotations

from config import FILL_IN_PLACEHOLDER
from lab_store import load_answers


def step_variables(module) -> list[str]:
    names: list[str] = []
    for step in getattr(module, "STEPS", []):
        for var in step.get("variables", []):
            if var not in names:
                names.append(var)
    return names


def inject_answers(module) -> None:
    answers = load_answers()
    for var in step_variables(module):
        setattr(module, var, answers.get(var, FILL_IN_PLACEHOLDER))
