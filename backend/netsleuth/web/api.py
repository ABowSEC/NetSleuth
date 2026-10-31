"""HTTP API v1 (docs/API_CONTRACT.md) plus static hosting of the exported UI."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, Flask, Response, abort, jsonify, request, send_from_directory

from .. import __version__
from ..core.events import EventEngine
from ..core.identify_mode import AlreadyRunning, IdentifySession, MonitoringPaused
from ..core.pipeline import Pipeline
from ..core.store import DeviceStore
from ..settings import Settings
from ..utils.mac import normalize_mac

log = logging.getLogger(__name__)

DEV_ORIGIN = "http://localhost:3000"
EVENT_KINDS = {"joined", "left", "new_device", "ip_changed", "mac_conflict", "alert", "identified"}
IDLE_IDENTIFY = {"running": False, "started_at": None, "ends_at": None, "done": 0, "total": 0,
                 "current": None, "port_check": False}
MAX_STREAMS = 8
STREAM_PING_S = 15
STREAM_SUMMARY_S = 2
NAME_MAX = 64
NOTES_MAX = 500


@dataclass
class AppContext:
    store: DeviceStore
    engine: EventEngine
    settings: Settings
    pipeline: Pipeline | None = None
    interface: str | None = None
    dev: bool = False
    static_dir: Path | None = None
    save_settings: bool = True
    identify: IdentifySession | None = None


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def create_app(ctx: AppContext) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False
    api = Blueprint("api", __name__, url_prefix="/api/v1")
    streams = {"open": 0}
    streams_lock = threading.Lock()

    # ── Guards and errors ────────────────────────────────────────────────────

    @app.before_request
    def guard_writes():
        if not request.path.startswith("/api/") or request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        origin = request.headers.get("Origin")
        if origin:
            own = f"{request.scheme}://{request.host}"
            allowed = {own} | ({DEV_ORIGIN} if ctx.dev else set())
            if origin.rstrip("/") not in allowed:
                raise ApiError(403, "forbidden_origin", "Cross-site request refused.")
        if request.mimetype != "application/json":
            raise ApiError(415, "unsupported_media_type", "Send Content-Type: application/json.")
        return None

    @app.errorhandler(ApiError)
    def api_error(e: ApiError):
        return jsonify(error=e.code, message=e.message), e.status

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(error="not_found", message="Not found."), 404
        return e

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="method_not_allowed", message="Method not allowed."), 405

    @app.errorhandler(500)
    def server_error(e):
        log.exception("Unhandled API error")
        return jsonify(error="internal", message="Internal server error."), 500

    def body() -> dict:
        if not request.get_data():
            return {}
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "bad_json", "Request body must be a JSON object.")
        return data

    def path_mac(mac: str) -> str:
        normalized = normalize_mac(mac)
        if not normalized:
            raise ApiError(404, "not_found", "No such device.")
        return normalized

    def int_arg(name: str, default: int | None, lo: int, hi: int) -> int | None:
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            raise ApiError(400, "bad_query", f"{name} must be an integer.") from None
        if not lo <= value <= hi:
            raise ApiError(400, "bad_query", f"{name} must be between {lo} and {hi}.")
        return value

    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "capturing": bool(ctx.pipeline and not ctx.pipeline.paused),
            "interface": ctx.interface,
        }

    # ── Status ───────────────────────────────────────────────────────────────

    @api.get("/health")
    def get_health():
        return health()

    @api.get("/summary")
    def get_summary():
        return ctx.store.summary()

    @api.post("/capture/pause")
    def pause():
        body()
        if ctx.pipeline:
            ctx.pipeline.pause()
        return health()

    @api.post("/capture/resume")
    def resume():
        body()
        if ctx.pipeline:
            ctx.pipeline.resume()
        return health()

    # ── Devices ──────────────────────────────────────────────────────────────

    @api.get("/devices")
    def list_devices():
        status = request.args.get("status", "all")
        if status not in ("all", "online", "offline"):
            raise ApiError(400, "bad_query", "status must be all, online or offline.")
        known_raw = request.args.get("known")
        if known_raw not in (None, "true", "false"):
            raise ApiError(400, "bad_query", "known must be true or false.")
        known = None if known_raw is None else known_raw == "true"
        devices = ctx.store.list_devices(status=status, known=known, q=request.args.get("q"))
        return jsonify([d.to_api() for d in devices])

    @api.get("/devices/<mac>")
    def get_device(mac):
        detail = ctx.store.detail(path_mac(mac))
        if detail is None:
            raise ApiError(404, "not_found", "No such device.")
        return detail

    @api.patch("/devices/<mac>")
    def patch_device(mac):
        mac = path_mac(mac)
        data = body()
        unknown = set(data) - {"name", "is_known", "notes"}
        if unknown:
            raise ApiError(400, "bad_field", f"Unknown field(s): {', '.join(sorted(unknown))}.")
        changes = {}
        for key, limit in (("name", NAME_MAX), ("notes", NOTES_MAX)):
            if key in data:
                value = data[key]
                if value is not None and not isinstance(value, str):
                    raise ApiError(400, "bad_field", f"{key} must be a string or null.")
                value = (value or "").strip() or None
                if value and len(value) > limit:
                    raise ApiError(400, "bad_field", f"{key} must be at most {limit} characters.")
                changes[key] = value
        if "is_known" in data:
            if not isinstance(data["is_known"], bool):
                raise ApiError(400, "bad_field", "is_known must be a boolean.")
            changes["is_known"] = data["is_known"]
        device = ctx.store.update(mac, **changes)
        if device is None:
            raise ApiError(404, "not_found", "No such device.")
        return device.to_api()

    @api.delete("/devices/<mac>")
    def delete_device(mac):
        body()
        if not ctx.store.forget(path_mac(mac)):
            raise ApiError(404, "not_found", "No such device.")
        return "", 204

    # ── Events ───────────────────────────────────────────────────────────────

    @api.get("/events")
    def list_events():
        kind = request.args.get("kind")
        if kind and kind not in EVENT_KINDS:
            raise ApiError(400, "bad_query", f"kind must be one of {', '.join(sorted(EVENT_KINDS))}.")
        mac = request.args.get("mac")
        return jsonify(ctx.store.list_events(
            since=int_arg("since", None, 0, 2**63 - 1),
            limit=int_arg("limit", 100, 1, 1000),
            kind=kind,
            mac=normalize_mac(mac) if mac else None,
        ))

    @api.get("/events/export")
    def export_events():
        payload = json.dumps(ctx.store.list_events(limit=100_000), indent=2)
        return Response(payload, mimetype="application/json", headers={
            "Content-Disposition": f'attachment; filename="netsleuth-events-{time.strftime("%Y%m%d-%H%M%S")}.json"',
        })

    @api.get("/stream")
    def stream():
        with streams_lock:
            if streams["open"] >= MAX_STREAMS:
                raise ApiError(503, "too_many_streams", "Too many open live connections.")
            streams["open"] += 1

        try:
            last_id = int(request.headers.get("Last-Event-ID", ""))
        except ValueError:
            last_id = None
        inbox: queue.Queue = queue.Queue(maxsize=256)

        def deliver(kind: str, payload: dict) -> None:
            try:
                inbox.put_nowait((kind, payload))
            except queue.Full:
                pass  # slow client; it can resync with Last-Event-ID

        unsubscribers = [ctx.engine.subscribe(lambda event: deliver("event", event))]
        if ctx.identify:
            unsubscribers.append(ctx.identify.subscribe(lambda status: deliver("identify", status)))

        def frame(kind: str, data: dict, event_id: int | None = None) -> str:
            head = f"id: {event_id}\n" if event_id is not None else ""
            return f"{head}event: {kind}\ndata: {json.dumps(data)}\n\n"

        def generate():
            try:
                if last_id is not None:
                    for event in reversed(ctx.store.list_events(since=last_id, limit=500)):
                        yield frame("event", event, event["id"])
                last_summary = None
                next_summary = next_ping = 0.0
                while True:
                    try:
                        kind, payload = inbox.get(timeout=1)
                        yield frame(kind, payload, payload["id"] if kind == "event" else None)
                    except queue.Empty:
                        pass
                    now = time.monotonic()
                    if now >= next_summary:
                        summary = ctx.store.summary()
                        comparable = {k: v for k, v in summary.items() if k != "last_update"}
                        if comparable != last_summary:
                            last_summary = comparable
                            yield frame("summary", summary)
                        next_summary = now + STREAM_SUMMARY_S
                    if now >= next_ping:
                        yield ": ping\n\n"
                        next_ping = now + STREAM_PING_S
            finally:
                for unsubscribe in unsubscribers:
                    unsubscribe()
                with streams_lock:
                    streams["open"] -= 1

        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ── Identify mode ────────────────────────────────────────────────────────

    def session() -> IdentifySession:
        if not ctx.identify:
            raise ApiError(503, "identify_unavailable", "Identify mode isn't available while capture is off.")
        return ctx.identify

    @api.get("/identify")
    def identify_status():
        return ctx.identify.status() if ctx.identify else IDLE_IDENTIFY

    @api.post("/identify/start")
    def identify_start():
        data = body()
        unknown = set(data) - {"minutes", "macs"}
        if unknown:
            raise ApiError(400, "bad_field", f"Unknown field(s): {', '.join(sorted(unknown))}.")
        minutes = data.get("minutes", ctx.settings.identify_minutes)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 30:
            raise ApiError(400, "bad_field", "minutes must be a whole number from 1 to 30.")
        macs = data.get("macs")
        if macs is not None:
            if not isinstance(macs, list) or not all(isinstance(m, str) for m in macs):
                raise ApiError(400, "bad_field", "macs must be a list of MAC addresses.")
            macs = [m for m in (normalize_mac(m) for m in macs) if m]
            if not macs:
                raise ApiError(400, "bad_field", "None of those MAC addresses are valid.")
        try:
            return session().start(minutes, macs)
        except AlreadyRunning:
            raise ApiError(409, "already_running", "Identify mode is already running.") from None
        except MonitoringPaused:
            raise ApiError(423, "monitoring_paused", "Resume monitoring before identifying devices.") from None

    @api.post("/identify/stop")
    def identify_stop():
        body()
        return session().stop(wait=2)

    # ── Settings ─────────────────────────────────────────────────────────────

    @api.get("/settings")
    def get_settings():
        return ctx.settings.to_dict()

    @api.patch("/settings")
    def patch_settings():
        data = body()
        candidate = Settings(**ctx.settings.to_dict())
        try:
            candidate.update(data)
        except ValueError as e:
            raise ApiError(400, "bad_field", str(e)) from None
        ctx.settings.update(data)
        if ctx.save_settings:
            ctx.settings.save()
        return ctx.settings.to_dict()

    app.register_blueprint(api)

    # ── Exported UI ──────────────────────────────────────────────────────────

    if ctx.static_dir and ctx.static_dir.is_dir():
        root = ctx.static_dir

        @app.get("/")
        @app.get("/<path:path>")
        def ui(path: str = ""):
            if path.startswith("api/"):
                abort(404)
            for candidate in (path, f"{path}.html", f"{path}/index.html"):
                if candidate and (root / candidate).is_file():
                    return send_from_directory(root, candidate)
            return send_from_directory(root, "index.html")

    return app


def default_static_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "frontend" / "out"


class Server:
    """waitress server that can be stopped from another thread."""

    def __init__(self, app: Flask, host: str, port: int):
        from waitress.server import create_server

        self._server = create_server(app, host=host, port=port, threads=16, channel_timeout=60)
        self._thread = threading.Thread(target=self._server.run, name="web", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.close()
