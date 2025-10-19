from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

def resolve_log_dir() -> Path:
    """
    Resolve where JSONL logs should be written. Priority:
      1) LOG_DIR env var
      2) ./logs next to this file
    """
    if os.environ.get("LOG_DIR"):
        p = Path(os.environ["LOG_DIR"])
    else:
        p = Path(__file__).resolve().parent / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p

LOG_DIR = resolve_log_dir()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def record_customer_interest(email: str, name: str, message: str) -> Dict[str, Any]:
    """
    Log a prospective customer's interest via print + JSONL.
    Returns a small payload for function_response -> model follow-up.
    """
    lead_id = str(uuid.uuid4())
    ts = _now_iso()

    if not EMAIL_RE.match(email or ""):
        print(f"[lead.invalid] {ts} id={lead_id} email={email!r}", flush=True)
        return {"ok": False, "error": "invalid_email", "lead_id": lead_id, "ts": ts}

    event = {"ts": ts, "event": "lead_recorded", "lead_id": lead_id, "email": email.strip(), "name": (name or "").strip(), "message": (message or "").strip()}
    preview = (event["message"][:120] + "…") if len(event["message"]) > 120 else event["message"]
    print(f"[lead] {ts} id={lead_id} {email} {event['name']} :: {preview}", flush=True)
    _append_jsonl(LOG_DIR / "leads.jsonl", event)
    return {"ok": True, "lead_id": lead_id, "ts": ts}

def record_feedback(question: str) -> Dict[str, Any]:
    """
    Log an unknown/missing-answer question via print + JSONL.
    """
    fb_id = str(uuid.uuid4())
    ts = _now_iso()
    q = (question or "").strip()

    event = {"ts": ts, "event": "feedback_recorded", "feedback_id": fb_id, "question": q}
    preview = (q[:140] + "…") if len(q) > 140 else q
    print(f"[feedback] {ts} id={fb_id} :: {preview}", flush=True)
    _append_jsonl(LOG_DIR / "feedback.jsonl", event)
    return {"ok": True, "feedback_id": fb_id, "ts": ts}


def get_function_declarations() -> list[dict]:
    """
    Return tool/function schemas in Gemini format (uppercase types).
    """
    return [
        {
            "name": "record_customer_interest",
            "description": (
                "Use when the user wants services or follow-up. "
                "Ask for missing fields first. Do NOT call if email/name/message are unknown."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "email":  {"type": "STRING", "description": "Customer email address."},
                    "name":   {"type": "STRING", "description": "Customer full name."},
                    "message":{"type": "STRING", "description": "Short note on project/needs/context."}
                },
                "required": ["email", "name", "message"]
            }
        },
        {
            "name": "record_feedback",
            "description": (
                "Use when the question is not answered by the provided SUMMARY/PDF or confidence is low. "
                "Do NOT guess. Pass the user's exact question."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "question": {"type": "STRING", "description": "The user question the bot failed to answer."}
                },
                "required": ["question"]
            }
        }
    ]

__all__ = ["LOG_DIR", "record_customer_interest", "record_feedback", "get_function_declarations"]