"""Loopback-only replay API. Raw private images and replay files are never served."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..infrastructure.paths import data_root, project_root
from ..infrastructure.storage import History
from .demo import demo_events, demo_sessions
from .review import answer


class ReviewRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=500)
    sequence: int | None = None


class CorrectionRequest(BaseModel):
    session_id: str
    sequence: int
    field: str
    corrected_value: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=500)


def create_app(history: History | None = None, model_root: Path | None = None,
               static_root: Path | None = None) -> FastAPI:
    database = history or History()
    reports = model_root or data_root() / "models"
    site = static_root or project_root() / "web" / "dist"
    app = FastAPI(title="雀魂麻将助手 · 本地复盘看板", version="0.3.0")

    def get_events(session_id: str):
        if session_id in ("demo-3p", "demo-4p"):
            return demo_events(int(session_id[5]))
        events = database.events(session_id)
        if not events:
            raise HTTPException(404, "未找到牌局事件")
        return events

    @app.get("/api/health")
    def health():
        return {"ok": True, "local_only": True, "version": "0.3.0"}

    @app.get("/api/sessions")
    def sessions():
        real = database.sessions()
        for row in real:
            snapshots = database.snapshots(row["id"])
            row["mode"] = snapshots[0]["board"]["mode"] if snapshots else None
            row["synthetic"] = False
        return real + demo_sessions()

    @app.get("/api/sessions/{session_id}/events")
    def events(session_id: str):
        return get_events(session_id)

    @app.get("/api/sessions/{session_id}/snapshots")
    def snapshots(session_id: str):
        if session_id.startswith("demo-"):
            return []
        get_events(session_id)
        return database.snapshots(session_id)

    @app.get("/api/metrics")
    def metrics():
        result = {}
        for mode in (3, 4):
            path = reports / f"{mode}p" / "report.json"
            result[str(mode)] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
                "mode": mode, "promoted": False, "reason": "尚无训练与独立测试报告"}
        return result

    @app.get("/api/cases")
    def cases():
        gaps = []
        for session in database.sessions():
            gaps += [event for event in database.events(session["id"])
                     if event["kind"] in ("tracking_gap", "river_removed_candidate")]
        return {"gaps": gaps[-50:], "corrections": database.corrections()[:50]}

    @app.post("/api/review")
    def review(request: ReviewRequest):
        return answer(get_events(request.session_id), request.question, request.sequence)

    @app.post("/api/corrections")
    def correction(request: CorrectionRequest):
        if request.session_id.startswith("demo-"):
            raise HTTPException(400, "合成演示事件不能作为训练修正")
        try:
            identifier = database.add_correction(request.session_id, request.sequence,
                                                  request.field, request.corrected_value, request.note)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return {"id": identifier, "stored_locally": True, "automatically_trained": False}

    if site.exists() and (site / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=site / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            target = (site / path).resolve()
            if target.is_relative_to(site.resolve()) and target.is_file():
                return FileResponse(target)
            return FileResponse(site / "index.html")
    else:
        @app.get("/")
        def no_frontend():
            return {"message": "Web 前端尚未构建。运行 npm install && npm run build（web 目录）。"}
    return app
