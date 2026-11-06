"""Tutor chat: conversations, messages, and streaming chat completions.

The stream is Server-Sent Events with JSON payloads:
    data: {"type": "delta", "content": "..."}
    data: {"type": "done", "assistant_id": 12}
    data: {"type": "error", "code": "...", "message": "..."}
"""
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .. import db
from ..errors import AppError
from ..ratelimit import check_limit
from ..schemas import ChatIn, ConversationIn, RenameIn
from ..services import ai
from ..services.progress import ensure_user, log_activity
from ..services import tutor

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "local"


def _own_conversation(user_id: int, conversation_id: int) -> dict:
    conv = db.query_one(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id),
    )
    if conv is None:
        raise AppError(404, "not_found", "Conversation not found.")
    return conv


def _default_mode(user_id: int) -> str:
    pref = db.query_one(
        "SELECT default_tutor_mode FROM preferences WHERE user_id = ?", (user_id,)
    )
    return pref["default_tutor_mode"] if pref else "learn"


def _list_item(c: dict, last_message: dict | None) -> dict:
    return {
        "id": c["id"],
        "title": c["title"],
        "mode": c["mode"],
        "created_at": c["created_at"],
        "updated_at": c["updated_at"],
        "preview": (last_message["content"][:80] if last_message else None),
        "message_count": db.query_one(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (c["id"],),
        )["n"],
    }


@router.get("")
def list_conversations():
    user = ensure_user()
    convs = db.query(
        "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
        (user["id"],),
    )
    items = []
    for c in convs:
        last = db.query_one(
            "SELECT * FROM messages WHERE conversation_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (c["id"],),
        )
        items.append(_list_item(c, last))
    return {"conversations": items}


@router.post("", status_code=201)
def create_conversation(body: ConversationIn):
    user = ensure_user()
    mode = body.mode or _default_mode(user["id"])
    title = (body.title or "New chat").strip()[:120]
    conv_id = db.execute(
        "INSERT INTO conversations (user_id, title, mode) VALUES (?, ?, ?)",
        (user["id"], title, mode),
    )
    log_activity(user["id"], "chat_started", str(conv_id), {"mode": mode})
    return db.query_one("SELECT * FROM conversations WHERE id = ?", (conv_id,))


@router.get("/{conversation_id}")
def get_conversation(conversation_id: int):
    user = ensure_user()
    conv = _own_conversation(user["id"], conversation_id)
    messages = db.query(
        "SELECT id, role, content, mode, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    )
    return {**conv, "messages": messages}


@router.patch("/{conversation_id}")
def rename_conversation(conversation_id: int, body: RenameIn):
    user = ensure_user()
    _own_conversation(user["id"], conversation_id)
    db.execute(
        "UPDATE conversations SET title = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (body.title.strip()[:120], conversation_id),
    )
    return db.query_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int):
    user = ensure_user()
    _own_conversation(user["id"], conversation_id)
    db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    return None


def _lesson_context(context) -> str:
    """If the student asked from inside a lesson, prime the tutor with it."""
    if context is None:
        return ""
    parts = []
    if context.lesson_slug:
        row = db.query_one(
            "SELECT l.title, l.summary, c.title AS course_title "
            "FROM lessons l JOIN courses c ON c.id = l.course_id "
            "WHERE l.slug = ?",
            (context.lesson_slug,),
        )
        if row:
            parts.append(
                f"The student is currently studying the lesson '{row['title']}' "
                f"(course: {row['course_title']}). Lesson summary: {row['summary']}"
            )
    elif context.course_slug:
        row = db.query_one(
            "SELECT title FROM courses WHERE slug = ?", (context.course_slug,)
        )
        if row:
            parts.append(f"The student is following the course '{row['title']}'.")
    if parts:
        return "Context: " + " ".join(parts)
    return ""


async def _stream_response(user_id: int, conversation_id: int,
                           user_content: str, mode: str, context) -> StreamingResponse:
    cfg = ai.require_provider_config()

    system = tutor.build_system_prompt(mode, user_id, _lesson_context(context))
    history = db.query(
        "SELECT role, content FROM messages WHERE conversation_id = ? "
        "ORDER BY id DESC LIMIT 30",
        (conversation_id,),
    )
    messages = tutor.build_messages(system, list(reversed(history)), user_content)

    async def event_stream():
        accumulated: list[str] = []
        error: dict | None = None
        try:
            async for piece in ai.stream_chat(
                cfg, messages, temperature=tutor.mode_temperature(mode)
            ):
                accumulated.append(piece)
                yield f'data: {json.dumps({"type": "delta", "content": piece})}\n\n'
        except AppError as e:
            error = {"code": e.code, "message": e.message}
            yield f'data: {json.dumps({"type": "error", **error})}\n\n'
        except asyncio.CancelledError:
            # Client pressed Stop (or disconnected): persist the partial answer.
            raise
        finally:
            content = "".join(accumulated)
            if content:
                db.execute(
                    "INSERT INTO messages (conversation_id, role, content, mode) "
                    "VALUES (?, 'assistant', ?, ?)",
                    (conversation_id, content, mode),
                )
                db.execute(
                    "UPDATE conversations SET updated_at = datetime('now') "
                    "WHERE id = ?",
                    (conversation_id,),
                )
            if error is None and content:
                log_activity(user_id, "chat_message", str(conversation_id),
                             {"chars": len(content)})
            elif error is not None:
                log_activity(user_id, "chat_error", str(conversation_id), error)

        if error is None:
            assistant_id = db.query_one(
                "SELECT id FROM messages WHERE conversation_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (conversation_id,),
            )
            yield f'data: {json.dumps({"type": "done", "assistant_id": assistant_id["id"] if assistant_id else None})}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _prepare_chat(user_id: int, conversation_id: int, body: ChatIn):
    conv = _own_conversation(user_id, conversation_id)
    mode = body.mode or conv["mode"]

    user_msg_id = db.execute(
        "INSERT INTO messages (conversation_id, role, content, mode) "
        "VALUES (?, 'user', ?, ?)",
        (conversation_id, body.content.strip(), mode),
    )

    # Give the conversation a real title from its first message.
    if conv["title"] == "New chat":
        title = body.content.strip().split("\n")[0][:60] or "New chat"
        db.execute("UPDATE conversations SET title = ? WHERE id = ?",
                   (title, conversation_id))

    if body.mode and body.mode != conv["mode"]:
        db.execute("UPDATE conversations SET mode = ? WHERE id = ?",
                   (body.mode, conversation_id))

    _ = user_msg_id
    return mode


@router.post("/{conversation_id}/chat")
async def chat(conversation_id: int, body: ChatIn, request: Request):
    user = ensure_user()
    check_limit("ai", _client_id(request))
    conv = _own_conversation(user["id"], conversation_id)

    mode = await _prepare_chat(user["id"], conversation_id, body)
    response = await _stream_response(
        user["id"], conversation_id, body.content, mode, body.context
    )
    _ = conv
    return response


@router.post("/{conversation_id}/retry")
async def retry(conversation_id: int, request: Request):
    """Delete the trailing assistant answer(s) and regenerate the last question."""
    user = ensure_user()
    check_limit("ai", _client_id(request))
    conv = _own_conversation(user["id"], conversation_id)

    last_user = db.query_one(
        "SELECT id, content, mode FROM messages WHERE conversation_id = ? "
        "AND role = 'user' ORDER BY id DESC LIMIT 1",
        (conversation_id,),
    )
    if last_user is None:
        raise AppError(400, "nothing_to_retry",
                        "There is no question to retry in this conversation yet.")
    db.execute(
        "DELETE FROM messages WHERE conversation_id = ? AND role = 'assistant' "
        "AND id > ?",
        (conversation_id, last_user["id"]),
    )
    return await _stream_response(
        user["id"], conversation_id, last_user["content"],
        last_user["mode"] or conv["mode"], None,
    )
