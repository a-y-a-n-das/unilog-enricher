"""
LLM Call Debug Instrumentation

Captures detailed information about every LLM API call for diagnostics.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEBUG_DIR = Path("debug/llm_calls")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

_summary_path = DEBUG_DIR / "summary.jsonl"
_call_counter = 0


def _estimate_tokens(text: str) -> int:
    """Lightweight token estimation: ~4 chars per token for English text."""
    if not text:
        return 0
    return len(text) // 4


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_summary(record: dict) -> None:
    with _summary_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_llm_call(
    *,
    stage: str,
    model: str,
    system_prompt: str | None,
    user_prompt: str,
    evidence: str = "",
    request_payload: dict | None = None,
    call_number: int = 1,
) -> str:
    """
    Log an LLM call request before it's made.
    Returns a unique call_id for matching with response.
    """
    global _call_counter
    _call_counter += 1
    call_id = f"{_call_counter:03d}_{stage.lower().replace(' ', '_').replace('/', '_')}"
    timestamp = datetime.now(timezone.utc).isoformat()

    system_chars = len(system_prompt) if system_prompt else 0
    user_chars = len(user_prompt) if user_prompt else 0
    evidence_chars = len(evidence) if evidence else 0
    total_chars = system_chars + user_chars + evidence_chars
    estimated_tokens = _estimate_tokens(system_prompt or "") + _estimate_tokens(user_prompt) + _estimate_tokens(evidence)

    print(f"[LLM DEBUG] stage={stage} model={model} chars={total_chars} estimated_tokens={estimated_tokens}", flush=True)

    request_data = {
        "call_id": call_id,
        "stage": stage,
        "timestamp": timestamp,
        "model": model,
        "call_number": call_number,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "evidence": evidence,
        "request_payload": request_payload,
        "sizes": {
            "system_prompt_chars": system_chars,
            "user_prompt_chars": user_chars,
            "evidence_chars": evidence_chars,
            "total_chars": total_chars,
            "estimated_tokens": estimated_tokens,
        },
    }

    request_file = DEBUG_DIR / f"{call_id}_request.json"
    _write_json(request_file, request_data)

    return call_id


def log_llm_response(
    *,
    call_id: str,
    stage: str,
    model: str,
    response_text: str,
    duration_ms: float,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Log an LLM call response after it completes."""
    timestamp = datetime.now(timezone.utc).isoformat()
    response_chars = len(response_text) if response_text else 0

    if success:
        print(f"[LLM DEBUG] stage={stage} success=true duration_ms={duration_ms:.0f} response_chars={response_chars}", flush=True)
    else:
        print(f"[LLM DEBUG] stage={stage} success=false duration_ms={duration_ms:.0f} error={error}", flush=True)

    response_data = {
        "call_id": call_id,
        "stage": stage,
        "timestamp": timestamp,
        "model": model,
        "response_text": response_text,
        "duration_ms": duration_ms,
        "success": success,
        "error": error,
        "sizes": {
            "response_chars": response_chars,
        },
    }

    response_file = DEBUG_DIR / f"{call_id}_response.json"
    _write_json(response_file, response_data)

    summary_record = {
        "call_id": call_id,
        "stage": stage,
        "model": model,
        "call_number": int(call_id.split("_")[0]),
        "success": success,
        "system_prompt_chars": 0,
        "user_prompt_chars": 0,
        "evidence_chars": 0,
        "total_chars": 0,
        "estimated_tokens": 0,
        "response_chars": response_chars,
        "duration_ms": duration_ms,
        "error": error,
    }

    request_file = DEBUG_DIR / f"{call_id}_request.json"
    if request_file.exists():
        try:
            req_data = json.loads(request_file.read_text(encoding="utf-8"))
            summary_record.update({
                "system_prompt_chars": req_data.get("sizes", {}).get("system_prompt_chars", 0),
                "user_prompt_chars": req_data.get("sizes", {}).get("user_prompt_chars", 0),
                "evidence_chars": req_data.get("sizes", {}).get("evidence_chars", 0),
                "total_chars": req_data.get("sizes", {}).get("total_chars", 0),
                "estimated_tokens": req_data.get("sizes", {}).get("estimated_tokens", 0),
            })
        except Exception:
            pass

    _append_summary(summary_record)


def log_llm_call_with_response(
    *,
    stage: str,
    model: str,
    system_prompt: str | None,
    user_prompt: str,
    evidence: str = "",
    request_payload: dict | None = None,
    call_number: int = 1,
    response_text: str,
    duration_ms: float,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Convenience function to log both request and response in one call."""
    call_id = log_llm_call(
        stage=stage,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evidence=evidence,
        request_payload=request_payload,
        call_number=call_number,
    )
    log_llm_response(
        call_id=call_id,
        stage=stage,
        model=model,
        response_text=response_text,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )