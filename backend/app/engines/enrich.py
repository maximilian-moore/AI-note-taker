"""LLM enrichment engines: cloud (Claude) + mock.

Pluggable per PRD.md §6.6 (FR-B3). Produces, from a transcript:
cleaned_text, title, category, tags, summary (meetings), and todos.
Returns a plain dict so callers stay engine-agnostic.
"""
from __future__ import annotations

import json
import logging
import re

from ..config import settings

log = logging.getLogger("pocketscribe.enrich")

_FILLERS = re.compile(
    r"\b(um+|uh+|erm+|ähm*|äh|halt|sozusagen|like|you know|kind of|i mean)\b[,]?\s*",
    re.IGNORECASE,
)
_ACTION_CUES = (
    "need to", "i should", "i have to", "must ", "todo", "to-do", "follow up",
    "follow-up", "action item", "let's", "remember to", "send ", "schedule ",
    "ich muss", "ich soll", "ich sollte", "erinnere", "nicht vergessen", "bezahlen",
)


def enrich(transcript: str, mode: str, language: str) -> dict:
    engine = settings.llm_engine
    if engine == "cloud" and not settings.anthropic_api_key:
        log.warning("llm_engine=cloud but ANTHROPIC_API_KEY is empty; using mock")
        engine = "mock"
    if engine == "cloud":
        try:
            return _enrich_cloud(transcript, mode, language)
        except Exception as e:  # never lose the note over an LLM hiccup
            log.exception("cloud enrichment failed, falling back to mock: %s", e)
    return _enrich_mock(transcript, mode, language)


# --- cloud (Claude) ----------------------------------------------------------
def _enrich_cloud(transcript: str, mode: str, language: str) -> dict:
    import anthropic  # lazy import

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    is_meeting = mode == "meeting"
    system = (
        "You clean up voice notes. Respond with a single JSON object and nothing else. "
        "Keys: title (short), category (one word), cleaned_text (the note with fillers, "
        "false starts and rambling removed but meaning preserved — DO NOT invent content), "
        "tags (array of short strings), summary (" +
        ("2-4 sentence summary of key points and decisions" if is_meeting else "empty string") +
        "), todos (array of objects with keys text, owner, due — owner/due may be null). "
        "Write title, cleaned_text and summary in the same language as the transcript "
        f"(detected: {language})."
    )
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": f"Mode: {mode}\n\nTranscript:\n{transcript}"}],
    )
    text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    data = json.loads(_extract_json(text))
    return _normalise(data, transcript, mode)


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end != -1 else "{}"


# --- mock (heuristic, no network) -------------------------------------------
def _enrich_mock(transcript: str, mode: str, language: str) -> dict:
    cleaned = _FILLERS.sub("", transcript)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
    words = cleaned.split()
    title = " ".join(words[:6]) + ("…" if len(words) > 6 else "") or "Untitled note"

    todos = []
    for s in sentences:
        low = s.lower()
        if any(cue in low for cue in _ACTION_CUES):
            todos.append({"text": s.rstrip("."), "owner": None, "due": None})

    summary = " ".join(sentences[:2]) if mode == "meeting" else ""
    category = _guess_category(cleaned)
    tags = _guess_tags(cleaned)
    return _normalise(
        {"title": title, "category": category, "cleaned_text": cleaned,
         "tags": tags, "summary": summary, "todos": todos},
        transcript, mode,
    )


def _guess_category(text: str) -> str:
    low = text.lower()
    table = {
        "Meeting": ("meeting", "call", "standup", "sync"),
        "Finance": ("invoice", "payment", "rechnung", "budget", "bezahlen"),
        "Design": ("design", "logo", "layout", "ui"),
        "Personal": ("buy", "groceries", "einkaufen", "family"),
    }
    for cat, kws in table.items():
        if any(k in low for k in kws):
            return cat
    return "General"


def _guess_tags(text: str) -> list[str]:
    low = text.lower()
    tags = []
    for kw in ("report", "logo", "invoice", "meeting", "design", "deadline", "rechnung"):
        if kw in low:
            tags.append(kw)
    return tags[:5]


def _normalise(data: dict, transcript: str, mode: str) -> dict:
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    todos = []
    for t in data.get("todos") or []:
        if isinstance(t, str):
            todos.append({"text": t, "owner": None, "due": None})
        elif isinstance(t, dict) and t.get("text"):
            todos.append({"text": t["text"], "owner": t.get("owner"), "due": t.get("due")})
    return {
        "title": (data.get("title") or "Untitled note").strip()[:120],
        "category": (data.get("category") or "General").strip()[:40],
        "cleaned_text": (data.get("cleaned_text") or transcript).strip(),
        "summary": (data.get("summary") or "").strip(),
        "tags": tags,
        "todos": todos,
    }
