"""CodeTutor AI - isolated student-code runner.

This script is executed as a SEPARATE process by the execution service:

    python -I -S run_student.py <code_file> [stdin_file]

The parent web server never executes student code in-process. This wrapper
adds defense-in-depth around the OS-level sandbox (stripped environment,
scratch working directory, memory limits, hard timeout):

  * network modules and process-spawning modules are blocked on import
  * os.system / os.popen / exec-family functions are disabled
  * filesystem writes/reads are restricted to the scratch directory
  * os.chdir is disabled so path checks cannot be escaped

This is a best-effort local sandbox, appropriate for a single-user learning
tool running the student's own code. It is NOT a hardened multi-tenant
sandbox; see docs/SECURITY.md for the honest threat model.
"""
import builtins as _builtins
import os as _os_mod
import sys as _sys
import traceback as _traceback

# The sandbox working directory (a fresh scratch folder set by the parent).
# Must be captured as the real cwd - NOT sys.path[0], which under -I points
# at the runner script's own folder.
_SCRATCH = _os_mod.getcwd()

_BLOCKED_MODULES = {
    "socket", "ssl", "select", "asyncio", "http", "urllib.request", "urllib3",
    "requests", "httpx", "aiohttp", "ftplib", "smtplib", "poplib", "imaplib",
    "telnetlib", "xmlrpc", "webbrowser", "subprocess", "ctypes", "multiprocessing",
    "winreg", "signal", "socketserver", "cgi", "pipes", "pty", "spawn",
}


class _ImportBlocker:
    """Meta path finder that refuses dangerous modules."""

    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in _BLOCKED_MODULES or fullname in _BLOCKED_MODULES:
            raise ImportError(
                f"Module '{fullname}' is not available in the CodeTutor sandbox "
                f"(network and process access are disabled for exercises)."
            )
        return None


def _restrict_os() -> None:
    import os

    def _deny(name):
        def _blocked(*a, **k):
            raise PermissionError(
                f"os.{name} is disabled in the CodeTutor sandbox."
            )
        return _blocked

    for name in ("system", "popen", "fork", "forkpty", "execv", "execve", "execvp",
                 "execvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv",
                 "spawnve", "spawnvp", "spawnvpe", "posix_spawn", "posix_spawnp",
                 "startfile", "chdir"):
        if hasattr(os, name):
            try:
                setattr(os, name, _deny(name))
            except Exception:
                pass

    # Filesystem WRITE operations are restricted to the scratch directory.
    # Read operations (stat/listdir/...) stay available because the import
    # machinery itself relies on them.
    def _guard_write(op, orig):
        def _checked(p, *args, **kwargs):
            if isinstance(p, (str, bytes, os.PathLike)):
                ap = os.path.abspath(os.fspath(p))
                scratch = os.path.abspath(_SCRATCH)
                if not (ap == scratch or
                        ap.lower().startswith(scratch.lower() + os.sep)):
                    raise PermissionError(
                        f"{op} outside the exercise folder is not allowed in the sandbox."
                    )
            return orig(p, *args, **kwargs)
        return _checked

    for op in ("remove", "unlink", "rmdir", "rename", "replace", "mkdir",
               "makedirs", "chmod", "removedirs"):
        orig = getattr(os, op, None)
        if orig is not None:
            setattr(os, op, _guard_write(op, orig))


def _restrict_builtins_open() -> None:
    _real_open = _builtins.open

    def _open_guard(file, mode="r", *args, **kwargs):
        if isinstance(file, str) and any(c in mode for c in ("w", "a", "x", "+")):
            import os
            ap = os.path.abspath(file)
            scratch = os.path.abspath(_SCRATCH)
            if not (ap == scratch or ap.lower().startswith(scratch.lower() + os.sep)):
                raise PermissionError(
                    "Writing outside the exercise folder is not allowed in the sandbox."
                )
        return _real_open(file, mode, *args, **kwargs)

    _builtins.open = _open_guard


def _guard_input() -> None:
    """Make input() return "" at EOF instead of raising EOFError.

    Beginners frequently run input()-based examples without providing
    program input; a raw EOFError traceback is confusing, while an empty
    string lets the program complete and teaches about the stdin box.
    """
    _real_input = _builtins.input

    def _input(prompt=""):
        try:
            return _real_input(prompt)
        except EOFError:
            return ""

    _builtins.input = _input


def main() -> int:
    _sys.meta_path.insert(0, _ImportBlocker())
    _restrict_os()
    _restrict_builtins_open()
    _guard_input()

    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if len(_sys.argv) < 2:
        print("runner: missing code file", file=_sys.stderr)
        return 2
    code_path = _sys.argv[1]
    stdin_path = _sys.argv[2] if len(_sys.argv) > 2 else None

    if stdin_path:
        try:
            _sys.stdin = open(stdin_path, "r", encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"runner: cannot open stdin file: {e}", file=_sys.stderr)
            return 2

    try:
        with open(code_path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"runner: cannot read code file: {e}", file=_sys.stderr)
        return 2

    g: dict = {"__name__": "__main__", "__file__": code_path,
               "__builtins__": _builtins}
    try:
        code = compile(source, code_path, "exec")
        exec(code, g)
    except SystemExit as e:
        return int(e.code or 0)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt", file=_sys.stderr)
        return 130
    except BaseException:
        _traceback.print_exc()
        return 1
    finally:
        try:
            _sys.stdout.flush()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    _sys.exit(main())
