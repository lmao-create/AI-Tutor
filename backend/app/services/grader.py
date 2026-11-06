"""Deterministic exercise grading.

Grading NEVER uses the AI. Known-answer kinds (mcq, predict_output,
fill_blank, find_bug) are compared server-side. write_program exercises are
graded by running the student's code against fixed test cases inside the
sandbox and comparing outputs - the expected values are fixed content, so
the result is reproducible. AI feedback (when a provider is configured) is
only ever a supplementary teaching aid on top of this result.
"""
import json
from typing import Optional

from ..config import settings
from ..services import execution


def normalize_text(value) -> str:
    """Whitespace-insensitive comparison for single-line answers."""
    return " ".join(str(value).split()).strip()


def normalize_output(value) -> str:
    """Trailing-whitespace-insensitive comparison for program output."""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


_HARNESS_TEMPLATE = '''
import builtins as _ct_builtins
import json as _ct_json
import ast as _ct_ast
_ct_calls = _ct_json.loads("""__CT_CALLS_JSON__""")
_ct_results = []
for _ct_t in _ct_calls:
    try:
        _ct_got = repr(eval(_ct_t["call"], globals()))
    except Exception as _ct_e:
        _ct_results.append({"call": _ct_t["call"], "ok": False, "error": repr(_ct_e)})
        continue
    _ct_exp = _ct_t["expected"]
    _ct_ok = _ct_got == _ct_exp
    if not _ct_ok:
        try:
            _ct_ok = _ct_ast.literal_eval(_ct_got) == _ct_ast.literal_eval(_ct_exp)
        except Exception:
            pass
    _ct_results.append({"call": _ct_t["call"], "ok": bool(_ct_ok),
                        "got": _ct_got, "expected": _ct_exp})
_ct_builtins.print("__CT__RESULT__" + _ct_json.dumps(_ct_results))
'''


def _fail(message: str, run: Optional[dict] = None) -> dict:
    return {"passed": False, "feedback": {"message": message}, "run": run,
            "explanation": None}


def _grade_mcq(ex: dict, submission: dict) -> dict:
    answer = ex.get("answer") or {}
    selected = submission.get("choice")
    if not isinstance(selected, int):
        return _fail("Choose an answer before submitting.")
    passed = selected == answer.get("index")
    return {
        "passed": passed,
        "feedback": {
            "message": "Correct - nicely done!" if passed
            else "Not quite. Re-read the lesson section above, or take a hint "
                 "before trying again. The correct answer stays hidden so the "
                 "retry is worth it.",
            "selected": selected,
        },
        "explanation": ex.get("solution", {}).get("explanation") if passed else None,
    }


def _grade_predict_output(ex: dict, submission: dict) -> dict:
    answer = ex.get("answer") or {}
    got = submission.get("output", "")
    expected = answer.get("output", "")
    passed = normalize_output(got) == normalize_output(expected)
    return {
        "passed": passed,
        "feedback": {
            "message": "Exactly right!" if passed
            else "That is not what this code prints. Tip: walk through the "
                 "code line by line on paper first - what does each line do "
                 "before anything is printed?",
            "your_answer": str(got)[:200],
        },
        "explanation": ex.get("solution", {}).get("explanation") if passed else None,
    }


def _grade_fill_blank(ex: dict, submission: dict) -> dict:
    answer = ex.get("answer") or {}
    got = submission.get("text", "")
    passed = normalize_text(got) == normalize_text(answer.get("text", ""))
    return {
        "passed": passed,
        "feedback": {
            "message": "Correct!" if passed
            else "Not the right fill-in. Check the syntax rules from the "
                 "lesson - small details like brackets or quotes matter.",
            "your_answer": str(got)[:200],
        },
        "explanation": ex.get("solution", {}).get("explanation") if passed else None,
    }


def _grade_find_bug(ex: dict, submission: dict) -> dict:
    answer = ex.get("answer") or {}
    selected = submission.get("line")
    if not isinstance(selected, int):
        return _fail("Pick the line number you think is broken.")
    passed = selected == answer.get("line")
    return {
        "passed": passed,
        "feedback": {
            "message": "You found it!" if passed
            else "That line is fine. Ask yourself: which line would make the "
                 "program crash or produce the wrong result, and why?",
            "selected": selected,
        },
        "explanation": ex.get("solution", {}).get("explanation") if passed else None,
    }


def _run_summary(result: execution.ExecResult) -> dict:
    return result.to_dict()


def _grade_write_program(ex: dict, submission: dict) -> dict:
    code = submission.get("code", "")
    if not code.strip():
        return _fail("Submit your code before grading.")
    spec = ex.get("test_spec") or {}
    spec_type = spec.get("type")

    if spec_type == "function":
        tests = spec.get("tests", [])
        if not tests:
            return _fail("This exercise has no test cases configured.")
        harness = _HARNESS_TEMPLATE.replace(
            "__CT_CALLS_JSON__", json.dumps(tests))
        result = execution.run_python(
            code + "\n\n" + harness,
            timeout_s=settings.exec_timeout_default,
        )
        run = _run_summary(result)
        if result.timed_out:
            return _fail(
                f"Your program ran for more than {settings.exec_timeout_default}s "
                "and was stopped. Look for an infinite loop (a while/for that "
                "never ends).", run)
        marker = None
        for line in result.stdout.splitlines():
            if line.startswith("__CT__RESULT__"):
                marker = line[len("__CT__RESULT__"):]
        if marker is None:
            if result.error_info:
                ei = result.error_info
                return _fail(
                    f"Your code raised {ei.get('type', 'an error')}"
                    + (f" on line {ei['line']}" if ei.get("line") else "")
                    + f": {ei.get('message', '')}", run)
            return _fail(
                "The tests could not run - your program ended before the test "
                "harness could check it.", run)
        try:
            results = json.loads(marker)
        except ValueError:
            return _fail("Test results could not be parsed. Please report this "
                         "exercise.", run)
        passed_count = sum(1 for t in results if t.get("ok"))
        passed = passed_count == len(results) and len(results) > 0
        return {
            "passed": passed,
            "feedback": {
                "message": f"Passed {passed_count} of {len(results)} test"
                           f"{'s' if len(results) != 1 else ''}.",
                "tests": results,
            },
            "run": run,
            "explanation": ex.get("solution", {}).get("explanation") if passed else None,
        }

    if spec_type == "stdout":
        cases = spec.get("cases", [])
        if not cases:
            return _fail("This exercise has no test cases configured.")
        results = []
        run: Optional[dict] = None
        for i, case in enumerate(cases):
            res = execution.run_python(
                code, stdin=case.get("stdin", ""),
                timeout_s=settings.exec_timeout_default)
            run = _run_summary(res)
            if res.timed_out:
                return _fail(
                    f"Your program ran for more than {settings.exec_timeout_default}s "
                    "on test case " + str(i + 1) + " and was stopped. Look for an "
                    "infinite loop.", run)
            ok = normalize_output(res.stdout) == normalize_output(
                case.get("expected_output", ""))
            results.append({
                "case": i + 1,
                "ok": ok,
                "stdin": case.get("stdin", ""),
                "expected": case.get("expected_output", ""),
                "got": res.stdout,
            })
        passed_count = sum(1 for t in results if t["ok"])
        passed = passed_count == len(results)
        return {
            "passed": passed,
            "feedback": {
                "message": f"Passed {passed_count} of {len(results)} test"
                           f"{'s' if len(results) != 1 else ''}.",
                "tests": results,
            },
            "run": run,
            "explanation": ex.get("solution", {}).get("explanation") if passed else None,
        }

    return _fail("This exercise has no runnable test specification.")


_GRADERS = {
    "mcq": _grade_mcq,
    "predict_output": _grade_predict_output,
    "fill_blank": _grade_fill_blank,
    "find_bug": _grade_find_bug,
    "write_program": _grade_write_program,
}


def grade(exercise: dict, submission: dict) -> dict:
    """Grade a submission deterministically. Returns the feedback payload."""
    grader = _GRADERS.get(exercise.get("kind"))
    if grader is None:
        return _fail("Unknown exercise type.")
    result = grader(exercise, submission)
    result["kind"] = exercise.get("kind")
    return result


def hint_payload(exercise: dict, revealed_count: int) -> dict:
    """Return the next hint (or the solution once hints are exhausted).

    `revealed_count` is the number of hints this user has already seen,
    so hints are revealed one at a time, in order - never all at once.
    """
    hints = exercise.get("hints") or []
    if revealed_count < len(hints):
        level = revealed_count + 1
        return {
            "type": "hint",
            "level": level,
            "total_hints": len(hints),
            "content": hints[revealed_count],
            "solution_available_after": len(hints) - level,
        }
    solution = exercise.get("solution") or {}
    return {
        "type": "solution",
        "level": len(hints) + 1,
        "total_hints": len(hints),
        "code": solution.get("code", ""),
        "explanation": solution.get("explanation", ""),
    }


def solution_payload(exercise: dict) -> dict:
    solution = exercise.get("solution") or {}
    return {
        "code": solution.get("code", ""),
        "explanation": solution.get("explanation", ""),
        "hints": exercise.get("hints") or [],
    }
