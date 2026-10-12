import importlib
import traceback

from flask import Flask, jsonify, render_template, request, send_from_directory

from config import get_org_config_status
from lab_api_cache import cached as cache_get, invalidate, invalidate_prefix
from lab_context import inject_answers
from lab_credentials import clear_credentials
from progress import get_all_progress
from settings import save_connection

app = Flask(__name__)

MODULE_IMPORTS = [
    "modules.module1_users",
    "modules.module2_org_data",
    "modules.module3_graphql",
    "modules.module4_webex_apis",
]


def get_modules():
    modules = []
    for name in MODULE_IMPORTS:
        mod = importlib.import_module(name)
        inject_answers(mod)
        modules.append(mod)
    return modules


def get_module_by_id(module_id: str):
    return next((m for m in get_modules() if m.MODULE_ID == module_id), None)


def _refresh_requested() -> bool:
    return str(request.args.get("refresh", "")).lower() in ("1", "true", "yes")


def json_cached(cache_key, loader, ttl=300):
    try:
        return jsonify(cache_get(cache_key, loader, force=_refresh_requested(), ttl=ttl))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _progress_payload():
    modules = get_modules()
    progress = get_all_progress(modules)
    config_status = get_org_config_status()
    progress["setup_complete"] = config_status["setup_complete"]
    return progress, config_status


@app.route("/LICENSE")
def license_text():
    return send_from_directory(app.root_path, "LICENSE", mimetype="text/plain")


@app.route("/")
@app.route("/dashboard")
def dashboard():
    progress, config_status = _progress_payload()
    return render_template(
        "dashboard.html",
        progress=progress,
        token_configured=config_status["token_configured"],
        org_configured=config_status["org_configured"],
        org_id_mismatch=config_status["org_id_mismatch"],
        org_id=config_status["org_id"],
        token_org_id=config_status["token_org_id"],
        setup_complete=config_status["setup_complete"],
        credential_source=config_status.get("credential_source", "none"),
        auth_method=config_status.get("auth_method", ""),
    )


@app.route("/api/config/status")
def api_config_status():
    return jsonify(get_org_config_status())


@app.route("/api/config", methods=["POST"])
def api_save_config():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"valid": False, "message": "Expected a JSON object."}), 400

    keep_existing = bool(payload.get("keep_existing_token"))
    result = save_connection(
        payload.get("token") or "",
        payload.get("org_id") or "",
        keep_existing_token=keep_existing,
    )
    if not result.get("valid"):
        return jsonify(result), 422

    invalidate_prefix("")
    return jsonify({"valid": True, "message": result.get("message"), "config_status": get_org_config_status()})


@app.route("/api/config/reset", methods=["POST"])
def api_reset_config():
    clear_credentials()
    invalidate_prefix("")
    return jsonify({"valid": True, "config_status": get_org_config_status()})


@app.route("/api/progress")
def api_progress():
    progress, _config = _progress_payload()
    return jsonify(progress)


# --- Users ---
@app.route("/api/users")
def api_users():
    def load():
        module1 = get_module_by_id("module1")
        return {"users": module1.fetch_users()}

    return json_cached("users", load)


# --- Org Data ---
@app.route("/api/org/entry-points")
def api_entry_points():
    def load():
        module2 = get_module_by_id("module2")
        return {"entry_points": module2.fetch_entry_points()}

    return json_cached("org:entry_points", load)


@app.route("/api/org/queues")
def api_queues():
    def load():
        module2 = get_module_by_id("module2")
        return {"queues": module2.fetch_queues()}

    return json_cached("org:queues", load)


@app.route("/api/org/global-variables")
def api_global_variables():
    def load():
        module2 = get_module_by_id("module2")
        return {"global_variables": module2.fetch_global_variables()}

    return json_cached("org:global_variables", load)


@app.route("/api/org/global-variables/<variable_id>", methods=["GET"])
def api_get_global_variable(variable_id):
    try:
        module2 = get_module_by_id("module2")
        return jsonify(module2.get_global_variable_edit_form(variable_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/org/global-variables/<variable_id>", methods=["PUT"])
def api_update_global_variable(variable_id):
    try:
        module2 = get_module_by_id("module2")
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Expected a JSON object"}), 400
        if "value" in payload and "defaultValue" not in payload:
            payload["defaultValue"] = payload.get("value")
        updated = module2.update_global_variable(variable_id, payload)
        invalidate("org:global_variables")
        return jsonify({"global_variable": updated})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/org/aux-codes")
def api_aux_codes():
    def load():
        module2 = get_module_by_id("module2")
        return {"aux_codes": module2.fetch_aux_codes()}

    return json_cached("org:aux_codes", load)


@app.route("/api/org/teams")
def api_teams():
    def load():
        module2 = get_module_by_id("module2")
        return {"teams": module2.fetch_teams()}

    return json_cached("org:teams", load)


# --- GraphQL Reports ---
@app.route("/api/reports/csr")
def api_csr():
    def load():
        module3 = get_module_by_id("module3")
        return {"records": module3.fetch_csr_report()}

    return json_cached("reports:csr", load)


@app.route("/api/reports/car")
def api_car():
    try:
        module3 = get_module_by_id("module3")
        return jsonify({"records": module3.fetch_car_report()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/asr")
def api_asr():
    def load():
        module3 = get_module_by_id("module3")
        return {"records": module3.fetch_asr_report()}

    return json_cached("reports:asr", load)


@app.route("/api/reports/aar")
def api_aar():
    try:
        module3 = get_module_by_id("module3")
        return jsonify({"records": module3.fetch_aar_report()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/csr-details")
def api_csr_details():
    try:
        module3 = get_module_by_id("module3")
        return jsonify({"records": module3.fetch_csr_details()})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/reports/car/<task_id>")
def api_car_for_task(task_id):
    try:
        module3 = get_module_by_id("module3")
        car = module3.fetch_car_for_task(task_id)
        return jsonify({"records": car["records"], "entry_point": car["entry_point"], "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/asr-details")
def api_asr_details():
    try:
        module3 = get_module_by_id("module3")
        return jsonify({"records": module3.fetch_asr_details()})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/api/reports/aar/<agent_session_id>")
def api_aar_for_session(agent_session_id):
    try:
        module3 = get_module_by_id("module3")
        return jsonify(
            {"records": module3.fetch_aar_for_session(agent_session_id), "agent_session_id": agent_session_id}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/query/<report_id>")
def api_report_query(report_id):
    try:
        module3 = get_module_by_id("module3")
        return jsonify(
            module3.get_report_query(
                report_id,
                task_id=request.args.get("task_id"),
                session_id=request.args.get("session_id"),
            )
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/rt-agents")
def api_rt_agents():
    try:
        module3 = get_module_by_id("module3")
        return jsonify({"agents": module3.fetch_rt_agents()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Webex APIs ---
@app.route("/api/webex/people")
def api_webex_people():
    def load():
        module4 = get_module_by_id("module4")
        return {"people": module4.fetch_webex_people()}

    return json_cached("webex:people", load)


@app.route("/api/webex/locations")
def api_locations():
    def load():
        module4 = get_module_by_id("module4")
        return {"locations": module4.fetch_locations()}

    return json_cached("webex:locations", load)


@app.route("/api/webex/pstn/<location_id>")
def api_pstn(location_id):
    if _refresh_requested():
        invalidate(f"webex:pstn:{location_id}")

    def load():
        module4 = get_module_by_id("module4")
        return {"pstn": module4.fetch_pstn_connection(location_id)}

    return json_cached(f"webex:pstn_api:{location_id}", load)


@app.route("/api/webex/ep-pstn")
def api_ep_pstn():
    if _refresh_requested():
        invalidate_prefix("webex:pstn")
        invalidate_prefix("webex:pstn_api")

    def load():
        module4 = get_module_by_id("module4")
        return {"numbers": module4.fetch_ep_pstn_numbers()}

    return json_cached("webex:ep_pstn", load)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
