from flask import current_app, jsonify, request
from pinballctl.game import runtime
from . import api_bp


def install_api(bp, kind):
    @bp.get("/status")
    def status():
        return jsonify(ok=True, **runtime.snapshot(current_app.instance_path))

    @bp.post("/config")
    def config():
        try:
            values = request.get_json(silent=True)
            cfg = runtime.validate_config(kind, values)
            from ..rules import api as rules_api

            devices, _ = rules_api._build_hardware_devices(
                rules_api._load_mapping_rows()
            )
            outputs = {
                d["id"] for d in devices if d["deviceClass"] in ("output", "coil")
            }
            for device in cfg.get("devices", []):
                runtime.check(
                    not device.get("releaseOutput")
                    or device["releaseOutput"] in outputs,
                    "Release output must be a mapped output/coil",
                )
            watches = runtime.observation_rules(
                current_app.instance_path,
                game_config=cfg if kind == "game" else None,
                ball_config=cfg if kind == "ball" else None,
            )
            rules = rules_api._rules_path()
            from pinballctl.ops.rules_blob import build_rules_pd_bytes

            blob = (
                build_rules_pd_bytes(rules, extra_rules=watches)
                if rules.exists()
                else None
            )
            runtime.configure(current_app.instance_path, kind, cfg)
            if blob is not None:
                rules_api._rules_pd_path().parent.mkdir(parents=True, exist_ok=True)
                rules_api._rules_pd_path().write_bytes(blob)
                rules_api._write_rules_meta(blob)
            return jsonify(ok=True, config=cfg, syncRequired=True)
        except (ValueError, TypeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @bp.post("/command")
    def command():
        body = request.get_json(silent=True) or {}
        try:
            name = body.get("command")
            params = body.get("params") or {}
            allowed = (
                {"OBSERVE", "RECONCILE", "REQUEST_BALL_MOVEMENT"}
                if kind == "ball"
                else set(runtime.registry.COMMANDS) - {"REQUEST_BALL_MOVEMENT"}
            )
            runtime.check(name in allowed, "Unsupported command for this module")
            result = runtime.execute(
                current_app.instance_path,
                name,
                params,
                body.get("id"),
                authority="simulation" if name == "OBSERVE" else "operator",
            )
            return jsonify(result), 200 if result["ok"] else 409
        except (ValueError, TypeError, KeyError) as exc:
            return jsonify(ok=False, error=str(exc)), 400


install_api(api_bp, "game")
