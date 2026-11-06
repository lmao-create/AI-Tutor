"""Sandbox execution tests: correctness, timeouts, restrictions."""
import pytest

from app.services.execution import run_python


def test_basic_stdout_capture():
    r = run_python("print('hello')\nprint(1 + 2)")
    assert r.exit_code == 0
    assert "hello" in r.stdout
    assert "3" in r.stdout
    assert r.timed_out is False


def test_stdin_support():
    r = run_python("name = input()\nprint('Hi,', name)", stdin="Ada")
    assert r.exit_code == 0
    assert "Hi, Ada" in r.stdout


def test_input_at_eof_returns_empty_not_traceback():
    # Beginners run input()-based examples without providing program input.
    r = run_python("name = input()\nprint('Hi,', name + '!')")
    assert r.exit_code == 0
    assert "Hi, !" in r.stdout
    assert "EOFError" not in r.stderr


def test_extra_input_calls_at_eof_are_empty():
    # One line provided, two reads: the second read returns "" gracefully.
    r = run_python(
        "a = input()\nb = input()\nprint(a, b, sep=' | ')",
        stdin="Ada",
    )
    assert r.exit_code == 0
    assert "Ada | " in r.stdout
    assert "EOFError" not in r.stderr


def test_error_line_points_at_student_code():
    # The reported line must be the student's line, never the runner's frame.
    r = run_python("x = [1, 2]\nprint(x[9])")
    assert r.exit_code != 0
    assert r.error_info["type"] == "IndexError"
    assert r.error_info["line"] == 2


def test_timeout_kills_infinite_loop():
    r = run_python("while True:\n    pass", timeout_s=3)
    assert r.timed_out is True
    assert r.exit_code != 0
    assert r.error_info["type"] == "Timeout"


def test_syntax_error_reported_with_line():
    r = run_python("print('unclosed")
    assert r.exit_code != 0
    assert r.error_info["type"] == "SyntaxError"
    assert "unclosed" in r.stderr


def test_runtime_error_reported():
    r = run_python("x = 1 / 0")
    assert r.exit_code == 1
    assert r.error_info["type"] == "ZeroDivisionError"
    assert "ZeroDivisionError" in r.stderr


def test_network_modules_blocked():
    for module in ("socket", "subprocess", "ctypes", "multiprocessing"):
        r = run_python(f"import {module}")
        assert "not available in the CodeTutor sandbox" in r.stderr


def test_os_system_blocked():
    r = run_python("import os\nos.system('echo hacked')")
    assert "disabled in the CodeTutor sandbox" in r.stderr


def test_writing_outside_scratch_blocked():
    r = run_python("open('C:/Windows/temp_evil.txt', 'w')")
    assert "not allowed" in r.stderr


def test_writing_inside_scratch_allowed():
    r = run_python(
        "with open('data.txt', 'w') as f:\n"
        "    f.write('ok')\n"
        "print(open('data.txt').read())"
    )
    assert r.exit_code == 0
    assert "ok" in r.stdout


def test_environment_stripped_of_secrets(monkeypatch):
    monkeypatch.setenv("CODETUTOR_API_KEY", "super-secret-key-value")
    r = run_python("import os\nprint(os.environ)")
    assert "super-secret-key-value" not in r.stdout
    assert "CODETUTOR" not in r.stdout


def test_cwd_is_scratch_and_cleaned():
    import os
    from app.config import settings
    before = set(os.listdir(settings.exec_tmp_dir)) if settings.exec_tmp_dir.exists() else set()
    r = run_python("import os\nprint(os.getcwd())")
    assert "exec_tmp" in r.stdout
    after = set(os.listdir(settings.exec_tmp_dir)) if settings.exec_tmp_dir.exists() else set()
    assert before == after  # scratch folder removed after the run


def test_output_truncation(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_output_bytes", 256)
    r = run_python("for i in range(10000):\n    print('x' * 20)")
    assert r.truncated is True
    assert len(r.stdout) <= 260


def test_code_size_limit():
    from app.config import settings
    with pytest.raises(ValueError):
        run_python("x = 1\n" * (settings.max_code_chars // 4 + 10))


def test_imports_work_for_lessons():
    r = run_python(
        "import random\nimport json\nimport math\nprint(math.floor(2.7), "
        "json.dumps({'ok': True}), type(random.randint(1, 1)))")
    assert r.exit_code == 0
    assert "2" in r.stdout


def test_execution_endpoint_via_api(client):
    payload = {"language": "python", "code": "print('via api')", "stdin": ""}
    r = client.post("/api/execution/run", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "via api" in data["stdout"]
    assert data["timed_out"] is False


def test_execution_endpoint_rejects_unknown_language(client):
    r = client.post("/api/execution/run",
                    json={"language": "javascript", "code": "console.log(1)"})
    assert r.status_code == 422 or r.status_code == 400


def test_execution_endpoint_reports_timeout(client):
    r = client.post("/api/execution/run",
                    json={"language": "python", "code": "while True: pass",
                          "timeout": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["timed_out"] is True
    assert data["error_info"]["type"] == "Timeout"
