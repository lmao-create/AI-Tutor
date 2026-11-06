"""Deterministic grader tests: every exercise kind."""
import pytest

from app.services.grader import (grade, hint_payload, normalize_output,
                                 normalize_text, solution_payload)


def _ex(kind, answer=None, test_spec=None, hints=("h1", "h2"), solution=None):
    return {
        "kind": kind, "answer": answer, "test_spec": test_spec,
        "hints": list(hints), "solution": solution or
        {"code": "print('x')", "explanation": "the why"},
    }


def test_normalize_helpers():
    assert normalize_text("  Hello   World ") == "Hello World"
    assert normalize_output("a \r\nb\n") == "a\nb"
    assert normalize_output("  x  \n") == "x"


def test_grade_mcq_correct_and_wrong():
    ex = _ex("mcq", answer={"index": 2})
    ok = grade(ex, {"choice": 2})
    assert ok["passed"] is True
    assert ok["explanation"] == "the why"
    bad = grade(ex, {"choice": 0})
    assert bad["passed"] is False
    assert bad["explanation"] is None  # explanation not leaked on failure
    assert "not" in bad["feedback"]["message"].lower()


def test_grade_mcq_missing_choice():
    ex = _ex("mcq", answer={"index": 1})
    result = grade(ex, {})
    assert result["passed"] is False


def test_grade_predict_output_ignores_trailing_whitespace():
    ex = _ex("predict_output", answer={"output": "4 1 8"})
    result = grade(ex, {"output": "  4 1 8  \n"})
    assert result["passed"] is True


def test_grade_fill_blank_normalized():
    ex = _ex("fill_blank", answer={"text": "age"})
    assert grade(ex, {"text": " age "})["passed"] is True
    assert grade(ex, {"text": "AGE"})["passed"] is False  # case matters in code


def test_grade_find_bug():
    ex = _ex("find_bug", answer={"line": 2})
    assert grade(ex, {"line": 2})["passed"] is True
    assert grade(ex, {"line": 4})["passed"] is False
    assert grade(ex, {})["passed"] is False


def test_grade_write_program_function_type():
    spec = {"type": "function", "tests": [
        {"call": "add(2, 3)", "expected": "5"},
        {"call": "add(7, 0)", "expected": "7"},
    ]}
    ex = _ex("write_program", test_spec=spec)
    good = "def add(a, b):\n    return a + b"
    result = grade(ex, {"code": good})
    assert result["passed"] is True
    assert result["feedback"]["message"] == "Passed 2 of 2 tests."

    # a - b passes only the second test (7 - 0 == 7), fails the first.
    wrong = "def add(a, b):\n    return a - b"
    result = grade(ex, {"code": wrong})
    assert result["passed"] is False
    tests = result["feedback"]["tests"]
    assert tests[0]["ok"] is False and tests[1]["ok"] is True


def test_grade_write_program_numeric_equivalence():
    spec = {"type": "function", "tests": [
        {"call": "half(5)", "expected": "2.5"},
    ]}
    ex = _ex("write_program", test_spec=spec)
    # student returns int 2 where 2.5 expected -> must fail
    result = grade(ex, {"code": "def half(n):\n    return 2"})
    assert result["passed"] is False


def test_grade_write_program_student_code_raises():
    spec = {"type": "function", "tests": [{"call": "f()", "expected": "1"}]}
    ex = _ex("write_program", test_spec=spec)
    result = grade(ex, {"code": "def f():\n    return 1 / 0"})
    assert result["passed"] is False
    # the harness captures the error per test (student code + tests share
    # one process), so the failure is reported inside the test result
    assert "ZeroDivisionError" in result["feedback"]["tests"][0]["error"]


def test_grade_write_program_timeout_infinite_loop():
    spec = {"type": "function", "tests": [{"call": "f()", "expected": "1"}]}
    ex = _ex("write_program", test_spec=spec)
    result = grade(ex, {"code": "def f():\n    while True:\n        pass\n\nf()"})
    assert result["passed"] is False
    assert "infinite" in result["feedback"]["message"].lower()


def test_grade_write_program_stdout_type_with_stdin():
    spec = {"type": "stdout", "cases": [
        {"stdin": "Ada", "expected_output": "Hi, Ada!"},
        {"stdin": "Grace", "expected_output": "Hi, Grace!"},
    ]}
    ex = _ex("write_program", test_spec=spec)
    good = 'name = input()\nprint("Hi, " + name + "!")'
    result = grade(ex, {"code": good})
    assert result["passed"] is True

    wrong = 'name = input()\nprint("Hello " + name)'
    result = grade(ex, {"code": wrong})
    assert result["passed"] is False
    assert result["feedback"]["message"] == "Passed 0 of 2 tests."


def test_grade_write_program_empty_submission():
    ex = _ex("write_program", test_spec={"type": "function", "tests": []})
    result = grade(ex, {"code": ""})
    assert result["passed"] is False


def test_hint_payload_sequence():
    ex = _ex("mcq", hints=["one", "two"])
    h1 = hint_payload(ex, 0)
    assert h1["type"] == "hint" and h1["level"] == 1 and h1["content"] == "one"
    h2 = hint_payload(ex, 1)
    assert h2["level"] == 2 and h2["content"] == "two"
    sol = hint_payload(ex, 2)
    assert sol["type"] == "solution"
    assert sol["code"] == "print('x')"


def test_solution_payload():
    ex = _ex("mcq", hints=["h"])
    s = solution_payload(ex)
    assert s["explanation"] == "the why"
    assert s["hints"] == ["h"]


def test_grader_never_uses_ai():
    """Grading must work with no provider at all - pure determinism."""
    from app.services import ai
    assert ai.get_provider_config() is None
    ex = _ex("mcq", answer={"index": 1})
    assert grade(ex, {"choice": 1})["passed"] is True
