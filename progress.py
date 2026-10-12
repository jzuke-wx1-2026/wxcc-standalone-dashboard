"""Helpers for module field completeness (used by the data modules)."""

from config import FILL_IN_PLACEHOLDER
from lab_store import get_answer


def is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        return stripped != "" and stripped != FILL_IN_PLACEHOLDER
    return True


def is_setup_complete(modules: list) -> bool:
    """True when Module 0 (Setup) is fully complete, or when no setup module exists."""
    mod0 = next((m for m in modules if getattr(m, "MODULE_ID", "") == "module0"), None)
    if not mod0:
        return True
    progress = get_module_progress(mod0, modules)
    return progress["total_steps"] > 0 and progress["completed_steps"] == progress["total_steps"]


def _setup_step_complete(step_id: str) -> bool:
    from lab_credentials import has_org_id, has_token

    if step_id == "0.1":
        return has_token()
    if step_id == "0.2":
        return has_org_id() and has_token()
    return False


def get_step_access(module, step: dict, all_modules: list | None = None) -> str:
    """Return step access: complete, active (current), or locked (skip ahead)."""
    module_id = getattr(module, "MODULE_ID", "")
    if all_modules and module_id != "module0" and not is_setup_complete(all_modules):
        return "locked"

    steps = getattr(module, "STEPS", [])
    step_ids = [s["id"] for s in steps]
    if step["id"] not in step_ids:
        return "locked"
    idx = step_ids.index(step["id"])
    statuses = [get_step_status(module, s, all_modules)["complete"] for s in steps]
    if statuses[idx]:
        return "complete"
    first_incomplete = next((i for i, done in enumerate(statuses) if not done), len(steps))
    return "active" if idx == first_incomplete else "locked"


def is_step_unlocked(module, step_id: str, all_modules: list | None = None) -> bool:
    steps = getattr(module, "STEPS", [])
    step = next((s for s in steps if s["id"] == step_id), None)
    if not step:
        return False
    return get_step_access(module, step, all_modules) != "locked"


def get_step_status(module, step: dict, all_modules: list | None = None) -> dict:
    module_id = getattr(module, "MODULE_ID", "")
    if module_id == "module0":
        variables = step.get("variables", [])
        complete = _setup_step_complete(step["id"])
        filled_map = {var: _setup_step_complete(step["id"]) for var in variables}
        if step["id"] == "0.1":
            filled_map = {"SETUP_BEARER_TOKEN": complete}
        elif step["id"] == "0.2":
            from lab_credentials import has_org_id

            filled_map = {"SETUP_ORG_ID": has_org_id()}
        filled = list(filled_map.values())
        return {
            "id": step["id"],
            "label": step["label"],
            "complete": complete,
            "filled_count": sum(filled),
            "total_count": len(variables),
            "variables": filled_map,
        }

    variables = step.get("variables", [])
    filled = [is_filled(getattr(module, var, get_answer(var))) for var in variables]
    complete = all(filled) if variables else False
    return {
        "id": step["id"],
        "label": step["label"],
        "complete": complete,
        "filled_count": sum(filled),
        "total_count": len(variables),
        "variables": {
            var: is_filled(getattr(module, var, get_answer(var)))
            for var in variables
        },
    }


def get_module_progress(module, all_modules: list | None = None) -> dict:
    steps = getattr(module, "STEPS", [])
    step_statuses = [get_step_status(module, step, all_modules) for step in steps]
    completed = sum(1 for s in step_statuses if s["complete"])
    return {
        "module_id": getattr(module, "MODULE_ID", "unknown"),
        "module_name": getattr(module, "MODULE_NAME", "Unknown Module"),
        "steps": step_statuses,
        "completed_steps": completed,
        "total_steps": len(steps),
        "percent": round((completed / len(steps)) * 100) if steps else 0,
    }


def get_all_progress(modules: list) -> dict:
    module_progress = [get_module_progress(m, modules) for m in modules]
    total_steps = sum(m["total_steps"] for m in module_progress)
    completed_steps = sum(m["completed_steps"] for m in module_progress)
    setup_done = is_setup_complete(modules)
    return {
        "modules": module_progress,
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "percent": round((completed_steps / total_steps) * 100) if total_steps else 0,
        "setup_complete": setup_done,
    }
