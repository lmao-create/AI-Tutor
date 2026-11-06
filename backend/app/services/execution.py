"""Sandboxed Python execution for student code.

Isolation strategy (defense in depth):

1. Student code runs in a SEPARATE process - never in the web server.
2. The child is launched with `-I -S` (isolated mode, no site packages).
3. The child environment contains NO secrets - a minimal env with just
   SystemRoot and the interpreter directory on PATH.
4. The working directory is a fresh scratch folder under data/exec_tmp,
   created per run and deleted afterwards.
5. Hard wall-clock timeout (default 10s, max 20s) enforced by the parent.
6. Memory cap via Windows Job Object (256 MB) or POSIX rlimits.
7. The runner wrapper blocks network/process-spawning modules and
   restricts file writes to the scratch directory.

This is appropriate for a local, single-user learning tool running the
student's own code. It is not a hardened multi-tenant sandbox - the
honest threat model is documented in docs/SECURITY.md.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import settings

RUNNER_PATH = Path(__file__).resolve().parent.parent / "runner" / "run_student.py"


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    duration_ms: int = 0
    error_info: Optional[dict] = field(default=None)
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "error_info": self.error_info,
            "truncated": self.truncated,
        }


def _classify_error(stderr: str) -> Optional[dict]:
    """Extract a friendly, structured description for syntax/runtime errors.

    The line number must come from the STUDENT's file, not from this
    server's own frames (which appear first in a Python traceback).
    """
    m = re.search(r"^(\w*(?:Error|Exception|Exit)):\s*(.*)$", stderr, re.M)
    line_m = re.search(
        r'File "[^"]*student_code\.py", line (\d+)', stderr)
    info: dict = {}
    if m:
        info["type"] = m.group(1)
        info["message"] = m.group(2)[:300]
    if line_m:
        info["line"] = int(line_m.group(1))
    return info or None


def _child_env() -> dict:
    import os
    env = {"PATH": str(Path(sys.executable).parent)}
    if os.name == "nt":
        env["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")
    return env


# --------------------------------------------------------------------------
# Windows Job Object (memory limit + kill-on-close)
# --------------------------------------------------------------------------
_job_lock = threading.Lock()


def _windows_job_limits(pid: int, memory_mb: int) -> tuple[bool, Optional[int]]:
    """Attach the child to a Job Object with a memory cap.

    Returns (ok, job_handle). The caller MUST keep the handle open for the
    duration of the run and close it afterwards: with KILL_ON_JOB_CLOSE,
    closing the last handle terminates the child immediately.
    """
    try:
        import ctypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC_LIMITS(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class EXTENDED_LIMITS(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMITS),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

        with _job_lock:
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return False, None
            try:
                info = EXTENDED_LIMITS()
                info.BasicLimitInformation.LimitFlags = (
                    JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                )
                info.ProcessMemoryLimit = memory_mb * 1024 * 1024
                if not kernel32.SetInformationJobObject(
                    job, JobObjectExtendedLimitInformation, ctypes.byref(info),
                    ctypes.sizeof(info),
                ):
                    kernel32.CloseHandle(job)
                    return False, None
                h = kernel32.OpenProcess(
                    PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
                if not h:
                    kernel32.CloseHandle(job)
                    return False, None
                try:
                    ok = bool(kernel32.AssignProcessToJobObject(job, h))
                finally:
                    kernel32.CloseHandle(h)
                if not ok:
                    kernel32.CloseHandle(job)
                    return False, None
                return True, job  # caller keeps this open while the child runs
            except Exception:
                if job:
                    kernel32.CloseHandle(job)
                return False, None
    except Exception:
        return False, None


def _close_job_handle(handle: int) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(handle))
    except Exception:
        pass


def _posix_preexec(memory_mb: int, cpu_seconds: int):
    def _apply():
        import resource
        mem = memory_mb * 1024 * 1024
        for res, val in ((resource.RLIMIT_AS, (mem, mem)),
                         (resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))):
            try:
                resource.setrlimit(res, val)
            except (ValueError, OSError):
                pass
    return _apply


# --------------------------------------------------------------------------
# Synchronous core (runs in a worker thread)
# --------------------------------------------------------------------------
def run_python_sync(code: str, stdin: str = "",
                    timeout_s: Optional[int] = None) -> ExecResult:
    timeout = min(timeout_s or settings.exec_timeout_default, settings.exec_timeout_max)
    if len(code) > settings.max_code_chars:
        raise ValueError(
            f"Code is too long ({len(code)} chars, max {settings.max_code_chars})."
        )

    import os
    settings.exec_tmp_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="run_", dir=str(settings.exec_tmp_dir)))
    code_path = scratch / "student_code.py"
    stdin_path = scratch / "stdin.txt"
    code_path.write_text(code, encoding="utf-8")
    stdin_path.write_text(stdin, encoding="utf-8")

    argv = [sys.executable, "-I", "-S", str(RUNNER_PATH), str(code_path)]
    # ALWAYS attach the stdin file (possibly empty): input() then returns an
    # empty string at EOF instead of raising a raw EOFError - much gentler
    # for beginners who forget the stdin box.
    argv.append(str(stdin_path))

    kwargs: dict = {}
    if os.name != "nt":
        kwargs["preexec_fn"] = _posix_preexec(settings.exec_memory_mb, timeout)

    t0 = time.monotonic()
    timed_out = False
    stdout_b = b""
    stderr_b = b""
    exit_code = -1
    job_handle: Optional[int] = None

    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(scratch),
            env=_child_env(),
            stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs,
        )
        if os.name == "nt":
            _, job_handle = _windows_job_limits(proc.pid, settings.exec_memory_mb)

        try:
            if stdin:
                try:
                    stdout_b, stderr_b = proc.communicate(
                        input=stdin.encode("utf-8"), timeout=timeout
                    )
                except subprocess.TimeoutExpired:
                    timed_out = True
            else:
                stdout_b, stderr_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True

        if timed_out:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                stdout_b, stderr_b = proc.communicate(timeout=5)
            except Exception:
                pass
        exit_code = proc.returncode if proc.returncode is not None else -1
    except OSError as e:
        return ExecResult(
            stdout="", stderr=f"Failed to start the Python sandbox process: {e}",
            exit_code=-1, duration_ms=0,
            error_info={"type": "SandboxError", "message": str(e)[:300]},
        )
    finally:
        if job_handle is not None:
            _close_job_handle(job_handle)
        duration_ms = int((time.monotonic() - t0) * 1000)
        shutil.rmtree(scratch, ignore_errors=True)

    limit = settings.max_output_bytes
    truncated = len(stdout_b) > limit or len(stderr_b) > limit
    stdout = stdout_b[:limit].decode("utf-8", "replace")
    stderr = stderr_b[:limit].decode("utf-8", "replace")

    error_info = None
    if timed_out:
        error_info = {
            "type": "Timeout",
            "message": f"Execution exceeded the {timeout}s time limit and was stopped.",
        }
    elif exit_code != 0:
        error_info = _classify_error(stderr)

    _ = job_handle  # kept open above for the child's lifetime, now closed
    return ExecResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        error_info=error_info,
        truncated=truncated,
    )


def run_python(code: str, stdin: str = "",
               timeout_s: Optional[int] = None) -> ExecResult:
    """Synchronous entry point used by the grader and tests."""
    return run_python_sync(code, stdin, timeout_s)
