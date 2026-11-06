"""Pydantic request schemas (input validation) and sanitization helpers."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .services.tutor import MODES

MAX_CODE = 60_000
MAX_TEXT = 12_000


def _not_blank(v: str) -> str:
    if v is None:
        return v
    stripped = v.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return v


class ProviderConfigIn(BaseModel):
    provider_name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: Optional[str] = Field(default=None, max_length=600)

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("provider_name", "model")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class ProviderTestIn(BaseModel):
    # Test the saved config by default; allow testing unsaved draft values.
    provider_name: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


class PreferencesIn(BaseModel):
    theme: Optional[Literal["dark", "light"]] = None
    active_course: Optional[str] = Field(default=None, max_length=80)
    default_tutor_mode: Optional[str] = None
    editor_font_size: Optional[int] = Field(default=None, ge=10, le=24)

    @field_validator("default_tutor_mode")
    @classmethod
    def _mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        return v


class ConversationIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    mode: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        return v


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class TutorContextIn(BaseModel):
    course_slug: Optional[str] = None
    lesson_slug: Optional[str] = None


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_TEXT)
    mode: Optional[str] = None
    context: Optional[TutorContextIn] = None

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MODES:
            raise ValueError(f"mode must be one of {sorted(MODES)}")
        return v


class ExerciseSubmitIn(BaseModel):
    choice: Optional[int] = Field(default=None, ge=-10_000, le=10_000)
    output: Optional[str] = Field(default=None, max_length=2000)
    text: Optional[str] = Field(default=None, max_length=2000)
    line: Optional[int] = Field(default=None, ge=-10_000, le=10_000)
    code: Optional[str] = Field(default=None, max_length=MAX_CODE)


class QuizSubmitIn(BaseModel):
    answers: dict[str, int] = Field(min_length=1, max_length=20)

    @field_validator("answers")
    @classmethod
    def _ints(cls, v: dict) -> dict:
        for k, a in v.items():
            if not isinstance(a, int) or not (0 <= a <= 50):
                raise ValueError("answers must map question ids to option indexes")
        return v


class LessonCompleteIn(BaseModel):
    time_spent_seconds: int = Field(default=0, ge=0, le=86_400)


class ExecRunIn(BaseModel):
    language: Literal["python"] = "python"
    code: str = Field(min_length=1, max_length=MAX_CODE)
    stdin: Optional[str] = Field(default=None, max_length=10_000)
    timeout: Optional[int] = Field(default=None, ge=1, le=20)


EXPLAIN_MODES = [
    "explain", "line_by_line", "beginner", "find_bugs", "improvements",
    "algorithm", "complexity", "pseudocode", "comments", "refactor", "compare",
]


class ExplainIn(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_CODE)
    language: Optional[str] = Field(default="python", max_length=40)
    mode: str
    code_b: Optional[str] = Field(default=None, max_length=MAX_CODE)

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in EXPLAIN_MODES:
            raise ValueError(f"mode must be one of {EXPLAIN_MODES}")
        return v


class DebugIn(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_CODE)
    error_message: str = Field(default="", max_length=4000)
    expected: str = Field(default="", max_length=2000)
    actual: str = Field(default="", max_length=2000)


class ResetIn(BaseModel):
    confirm: bool


def sanitize_quiz(quiz: list[dict]) -> list[dict]:
    """Strip answers/explanations from quiz questions sent to the client."""
    return [
        {"id": q.get("id"), "question": q.get("question"),
         "options": q.get("options", [])}
        for q in quiz
    ]


def sanitize_exercise(row: dict) -> dict:
    """Exercise rows must never leak answers, hints or solutions.

    `answer`, `test_spec`, `hints` and `solution` are stripped before the
    row ever reaches the browser. Grading happens server-side only.
    `options` are safe - they are needed to render multiple choices.
    """
    out = {k: v for k, v in row.items()
           if k not in ("answer", "hints", "solution", "test_spec")}
    out["hint_count"] = len(row.get("hints") or [])
    return out
