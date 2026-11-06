"""AI tools: code explainer and debugging assistant.

Both stream SSE like the tutor chat. They REQUIRE a configured provider -
in demo mode the API returns a clear error and the UI offers guidance
instead of pretending to answer.
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..errors import AppError
from ..ratelimit import check_limit
from ..schemas import EXPLAIN_MODES, DebugIn, ExplainIn
from ..services import ai
from ..services.progress import ensure_user, log_activity

router = APIRouter(prefix="/tools", tags=["tools"])

EXPLAIN_MODE_META = {
    "explain": "Explain this code",
    "line_by_line": "Explain it line by line",
    "beginner": "Explain like I'm a complete beginner",
    "find_bugs": "Find bugs",
    "improvements": "Suggest improvements",
    "algorithm": "Explain the algorithm",
    "complexity": "Explain time and space complexity",
    "pseudocode": "Convert to pseudocode",
    "comments": "Generate comments",
    "refactor": "Refactor the code",
    "compare": "Compare two implementations",
}

EXPLAIN_INSTRUCTIONS = {
    "explain": (
        "Explain what this code does. Start with a one-sentence summary, then "
        "walk through the main parts in order of importance. Finish briefly "
        "with what the code is typically used for."
    ),
    "line_by_line": (
        "Explain this code line by line. Work through it top to bottom: quote "
        "each line (or small logical group) and explain it underneath. End "
        "with a 2-3 sentence summary of the overall flow."
    ),
    "beginner": (
        "Explain this code to a complete beginner who has never programmed. "
        "Define every technical term the moment you use it, use a friendly "
        "everyday analogy for the overall idea, and keep each explanation "
        "step tiny. No jargon without explanation."
    ),
    "find_bugs": (
        "Find bugs and likely problems in this code. For each problem: quote "
        "the exact problematic line, explain what goes wrong and when it "
        "would show up, and give the minimal fix as a code snippet. If there "
        "are no real bugs, say so honestly and list code smells instead. "
        "Never invent execution results - say what you EXPECT would happen "
        "and why."
    ),
    "improvements": (
        "Suggest concrete improvements to this code: readability, naming, "
        "structure, edge cases, and simplifications. For each suggestion show "
        "a small before/after snippet and one sentence on why it helps. "
        "Preserve the original behavior."
    ),
    "algorithm": (
        "Explain the algorithm this code implements: the core idea in plain "
        "words, the steps in order, and a short walkthrough with a tiny "
        "concrete example input."
    ),
    "complexity": (
        "Analyze the time and space complexity of this code. State the Big-O "
        "clearly, then explain WHY by pointing at the specific loops, calls or "
        "data structures that drive it. Mention best/average/worst cases when "
        "they differ."
    ),
    "pseudocode": (
        "Convert this code into clear numbered pseudocode. No language-"
        "specific syntax - plain steps a person could follow. Then add one "
        "sentence about the purpose of any non-obvious step."
    ),
    "comments": (
        "Generate helpful comments for this code: a short header docstring "
        "and per-section comments that explain WHY, not just what. Output the "
        "complete commented code in a single fenced block."
    ),
    "refactor": (
        "Refactor this code for readability and simplicity while preserving "
        "its behavior. Output the full refactored code in one fenced block, "
        "then list each change you made with a one-line reason."
    ),
    "compare": (
        "Compare Implementation A and Implementation B below. Analyze "
        "correctness, readability, performance and edge cases. Summarize with "
        "a small markdown table, then give a clear recommendation with "
        "reasons."
    ),
}


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "local"


@router.get("/explain/modes")
def explain_modes():
    return {"modes": [
        {"id": mid, "label": label, "description": EXPLAIN_INSTRUCTIONS[mid]}
        for mid, label in EXPLAIN_MODE_META.items()
    ]}


@router.post("/explain")
async def explain(body: ExplainIn, request: Request):
    check_limit("ai", _client_id(request))
    user = ensure_user()
    cfg = ai.require_provider_config()

    language = (body.language or "python").strip()
    instruction = EXPLAIN_INSTRUCTIONS[body.mode]
    prompt = (
        f"{instruction}\n\n"
        f"The code is written in {language}. This is a learning tool: explain "
        f"accurately, and if something is ambiguous or might behave "
        f"differently than it looks, say so. Never claim you executed the "
        f"code.\n\n"
        f"```{language}\n{body.code}\n```"
    )
    if body.mode == "compare" and body.code_b:
        prompt += (
            f"\n\nImplementation B:\n```{language}\n{body.code_b}\n```"
        )
        prompt = prompt.replace(
            "The code is written in",
            "Implementation A is written in", 1)
    messages = [
        {"role": "system",
         "content": "You are an expert programming teacher explaining code to "
                    "a student. Use Markdown with fenced code blocks. Be "
                    "precise; teach, do not just describe."},
        {"role": "user", "content": prompt},
    ]

    async def stream():
        parts: list[str] = []
        try:
            async for piece in ai.stream_chat(cfg, messages, temperature=0.3):
                parts.append(piece)
                yield f'data: {json.dumps({"type": "delta", "content": piece})}\n\n'
            log_activity(user["id"], "explain_used", body.mode,
                         {"chars": len(body.code)})
            yield f'data: {json.dumps({"type": "done"})}\n\n'
        except AppError as e:
            yield f'data: {json.dumps({"type": "error", "code": e.code, "message": e.message})}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.post("/debug")
async def debug_assist(body: DebugIn, request: Request):
    check_limit("ai", _client_id(request))
    user = ensure_user()
    cfg = ai.require_provider_config()

    prompt = (
        "A student needs help debugging their program. Here is everything "
        "they know:\n\n"
        f"## Their code\n```python\n{body.code}\n```\n\n"
        f"## Error message\n{body.error_message or '(they did not paste one)'}\n\n"
        f"## Expected behavior\n{body.expected or '(not described)'}\n\n"
        f"## Actual behavior\n{body.actual or '(not described)'}\n\n"
        "Help them as a patient teacher. Structure your answer as numbered "
        "sections:\n"
        "1. Likely cause - your best diagnosis, clearly stated.\n"
        "2. The concept - teach the underlying idea they are missing.\n"
        "3. Where - point at the problematic line(s), quoting them.\n"
        "4. The fix - a minimal change, as a code snippet.\n"
        "5. Why it works - one short paragraph.\n"
        "6. Verify - a specific test they can run to confirm the fix.\n\n"
        "Honesty rules: never invent execution results, never claim you ran "
        "the code, and say clearly when you are uncertain or when the "
        "information given is not enough to be sure."
    )
    messages = [
        {"role": "system",
         "content": "You are an expert, encouraging programming teacher. "
                    "You debug by teaching. Use Markdown with fenced code "
                    "blocks."},
        {"role": "user", "content": prompt},
    ]

    async def stream():
        parts: list[str] = []
        try:
            async for piece in ai.stream_chat(cfg, messages, temperature=0.3):
                parts.append(piece)
                yield f'data: {json.dumps({"type": "delta", "content": piece})}\n\n'
            log_activity(user["id"], "debug_used", "debug",
                         {"chars": len(body.code)})
            yield f'data: {json.dumps({"type": "done"})}\n\n'
        except AppError as e:
            yield f'data: {json.dumps({"type": "error", "code": e.code, "message": e.message})}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
