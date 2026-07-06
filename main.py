"""FastAPI app = the whole product.
Serves the chat control-panel, runs commands through the team, holds the
24/7 scheduler, and exposes a WhatsApp webhook."""
import os
import threading
import secrets

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import config
from app import db, agents, tools

config.check()
db.init()

app = FastAPI(title="Backend Office Team")
security = HTTPBasic()
scheduler = BackgroundScheduler(timezone=config.TZ)

HERE = os.path.dirname(__file__)


# ---------- auth ----------
def auth(cred: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(cred.password, config.APP_PASSWORD)
    if not ok:
        raise HTTPException(status_code=401, detail="wrong password",
                            headers={"WWW-Authenticate": "Basic"})
    return True


# ---------- run a command in the background ----------
def _run_and_store(command, task_id):
    db.set_task(task_id, status="running")
    try:
        result = agents.run_command(command)
        db.set_task(task_id, status="done", result=result)
        db.add_chat("assistant", result)
    except Exception as e:
        db.set_task(task_id, status="error", result=str(e))
        db.add_chat("assistant", f"[error] {e}")


def dispatch(command: str) -> int:
    tid = db.add_task(command)
    db.add_chat("user", command)
    threading.Thread(target=_run_and_store, args=(command, tid), daemon=True).start()
    return tid


# ---------- UI ----------
@app.get("/", response_class=HTMLResponse)
def home(_=Depends(auth)):
    with open(os.path.join(HERE, "web", "index.html"), encoding="utf-8") as f:
        return f.read()


# ---------- chat / commands ----------
@app.post("/api/command")
def api_command(body: dict, _=Depends(auth)):
    cmd = (body or {}).get("command", "").strip()
    if not cmd:
        raise HTTPException(400, "empty command")
    tid = dispatch(cmd)
    return {"task_id": tid}


@app.get("/api/history")
def api_history(_=Depends(auth)):
    return {"chat": db.history(), "tasks": db.recent_tasks(20),
            "pending": db.list_pending(), "schedules": db.list_schedules()}


# ---------- scheduling ----------
@app.post("/api/schedule")
def api_schedule(body: dict, _=Depends(auth)):
    cron = (body or {}).get("cron", "").strip()
    cmd = (body or {}).get("command", "").strip()
    if not cron or not cmd:
        raise HTTPException(400, "cron and command required")
    sid = db.add_schedule(cron, cmd)
    _register(sid, cron, cmd)
    return {"schedule_id": sid}


# ---------- confirmations ----------
@app.post("/api/confirm")
def api_confirm(body: dict, _=Depends(auth)):
    pid = (body or {}).get("id")
    approve = (body or {}).get("approve", False)
    item = db.pop_pending(pid)
    if not item:
        raise HTTPException(404, "not found")
    if not approve:
        return {"status": "discarded"}
    import json
    p = json.loads(item["payload"])
    if item["kind"] == "email":
        r = tools.send_email(p["to"], p["subject"], p["body"])
    else:
        r = tools.whatsapp_send(p["to"], p["text"])
    return {"status": "sent", "detail": r}


@app.get("/api/download")
def api_download(path: str, _=Depends(auth)):
    if not os.path.abspath(path).startswith(os.path.abspath(config.OUTPUT_DIR)):
        raise HTTPException(403, "forbidden")
    if not os.path.exists(path):
        raise HTTPException(404, "not found")
    return FileResponse(path)


# ---------- WhatsApp webhook (host this endpoint; Vercel/free ok too) ----------
@app.get("/webhook/whatsapp")
def wa_verify(request: Request):
    p = request.query_params
    if p.get("hub.verify_token") == config.WHATSAPP_VERIFY_TOKEN:
        return Response(content=p.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403, "bad token")


@app.post("/webhook/whatsapp")
async def wa_incoming(request: Request):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        msg = entry["messages"][0]
        text = msg["text"]["body"]
        dispatch(f"[via WhatsApp] {text}")
    except (KeyError, IndexError):
        pass
    return JSONResponse({"status": "ok"})


# ---------- scheduler wiring ----------
def _register(sid, cron, command):
    try:
        scheduler.add_job(
            dispatch, CronTrigger.from_crontab(cron, timezone=config.TZ),
            args=[command], id=f"sched-{sid}", replace_existing=True,
        )
    except Exception as e:
        print(f"[scheduler] bad cron {cron}: {e}")


@app.on_event("startup")
def _startup():
    for s in db.list_schedules():
        _register(s["id"], s["cron"], s["command"])
    if not scheduler.running:
        scheduler.start()
    print("Backend Office Team is live. Team ready 24/7.")
