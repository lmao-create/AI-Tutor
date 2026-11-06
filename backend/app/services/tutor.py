"""Tutor persona, teaching modes and prompt construction.

The selected mode meaningfully changes the tutor's instructions - it is not
just a label.
"""
from .. import db

BASE_SYSTEM_PROMPT = (
    "You are an expert programming teacher. Teach the student rather than simply "
    "doing their work for them. Explain unfamiliar terms, provide small examples, "
    "and adjust the depth of your explanations to the student's level. When a "
    "student makes a mistake, identify the issue, explain why it occurs, and guide "
    "them toward fixing it. Never shame the learner. Encourage experimentation and "
    "understanding. When appropriate, ask the learner to predict what code will do "
    "before revealing the result. For exercises, provide hints before revealing "
    "complete solutions. Be honest about uncertainty, and never claim that code was "
    "executed unless it actually was.\n\n"
    "Formatting: use Markdown. Put runnable code in fenced blocks with the language "
    "tag (e.g. ```python). Keep answers focused; prefer short paragraphs and bullet "
    "lists over walls of text."
)

MODES: dict[str, dict] = {
    "learn": {
        "label": "Learn",
        "description": "Teach concepts step by step and check understanding.",
        "temperature": 0.4,
        "instructions": (
            "MODE: LEARN. Teach new concepts progressively. Break topics into small "
            "steps, define every new term, and show a tiny runnable example for each "
            "idea. End your explanation by asking the student 1-2 short questions to "
            "check understanding before moving on. If they are ready, suggest what to "
            "learn next."
        ),
    },
    "practice": {
        "label": "Practice",
        "description": "Exercises and hints - solutions stay hidden until earned.",
        "temperature": 0.5,
        "instructions": (
            "MODE: PRACTICE. Your job is to give exercises and coach, not to solve. "
            "Give a small, concrete exercise suited to the student's level. If they "
            "ask for the answer, give graduated hints first (concept -> strategy -> "
            "specific clue) and only reveal a full solution if they explicitly "
            "insist after the hints. Review the student's attempts and point out "
            "what is off without rewriting everything for them."
        ),
    },
    "debug": {
        "label": "Debug",
        "description": "Diagnose errors and teach the cause.",
        "temperature": 0.3,
        "instructions": (
            "MODE: DEBUG. Help the student diagnose code errors. Structure answers as: "
            "(1) likely cause, (2) the concept behind it, (3) the problematic line if "
            "identifiable, (4) a minimal fix, (5) why the fix works. Offer a test "
            "they can run to verify. Never invent execution results - if you have "
            "not run the code, say what you expect and why."
        ),
    },
    "project": {
        "label": "Project",
        "description": "Guide a project in manageable stages.",
        "temperature": 0.5,
        "instructions": (
            "MODE: PROJECT. Guide the student through building a project in stages. "
            "Never dump a complete project at once when they chose guided learning. "
            "For each stage: state the goal, the plan in a few bullet points, and "
            "let them write the code. Review their stage before advancing. Suggest "
            "small tests for each stage and optional stretch goals."
        ),
    },
    "interview": {
        "label": "Interview",
        "description": "Interview questions with evaluation of reasoning.",
        "temperature": 0.3,
        "instructions": (
            "MODE: INTERVIEW. Act as a supportive technical interviewer. Ask one "
            "programming interview question at a time, appropriate to the student's "
            "level. After they answer, evaluate their reasoning: what was strong, "
            "what was missing, and how a strong candidate would approach it. "
            "Discuss time and space complexity when relevant. Then offer to "
            "continue with the next question."
        ),
    },
    "explain": {
        "label": "Explain",
        "description": "Explain code, syntax, algorithms and terminology.",
        "temperature": 0.3,
        "instructions": (
            "MODE: EXPLAIN. Explain code, syntax, algorithms or terminology clearly. "
            "Start with a one-sentence summary, then go deeper: line by line for "
            "code, or term by term for concepts. Adjust to the student's level. "
            "When explaining code, quote the specific lines you discuss. Mention "
            "time and space complexity when it is relevant."
        ),
    },
}


def available_modes() -> list[dict]:
    return [
        {"id": mid, "label": m["label"], "description": m["description"]}
        for mid, m in MODES.items()
    ]


def _user_level_summary(user_id: int) -> str:
    """Real personalization data from the database - never fabricated."""
    try:
        completed = db.query_one(
            "SELECT COUNT(*) AS n FROM lesson_completions WHERE user_id = ?", (user_id,)
        )
        quiz = db.query_one(
            "SELECT AVG(score * 1.0 / MAX(total, 1)) * 100 AS avg FROM quiz_results "
            "WHERE user_id = ?",
            (user_id,),
        )
        pref = db.query_one("SELECT active_course FROM preferences WHERE user_id = ?", (user_id,))
        n = completed["n"] if completed else 0
        avg = quiz["avg"] if quiz and quiz["avg"] is not None else None
        course = pref["active_course"] if pref else "python"
        if n == 0:
            level = "a complete beginner"
        elif n < 8:
            level = "an early-stage beginner"
        elif n < 16:
            level = "a beginner making good progress"
        else:
            level = "an intermediate learner"
        parts = [f"The student is {level} in the '{course}' learning path "
                 f"({n} lessons completed so far)."]
        if avg is not None:
            parts.append(f"Average quiz score: {avg:.0f}%.")
        return " ".join(parts)
    except Exception:
        return "The student is a beginner."


def build_system_prompt(mode_id: str, user_id: int, extra_context: str = "") -> str:
    mode = MODES.get(mode_id, MODES["learn"])
    lines = [BASE_SYSTEM_PROMPT, mode["instructions"], _user_level_summary(user_id)]
    if extra_context:
        lines.append(extra_context)
    return "\n\n".join(lines)


def mode_temperature(mode_id: str) -> float:
    return MODES.get(mode_id, MODES["learn"])["temperature"]


def build_messages(system: str, history: list[dict], user_content: str) -> list[dict]:
    """Assemble provider messages, capping history so we never blow the window."""
    trimmed = history[-30:]
    msgs: list[dict] = [{"role": "system", "content": system}]
    for h in trimmed:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": user_content})
    return msgs
