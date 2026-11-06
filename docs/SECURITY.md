# Security notes

## Where the API key lives

- The AI provider API key is stored **only on the backend**:
  - the local secrets file `data/secrets.json` (created via the Settings page),
    written with user-only permissions where the platform supports it; or
  - the environment variable `CODETUTOR_API_KEY` (see `.env.example`).
- The key is **never**:
  - sent to the browser in any API response (the Settings API returns a masked
    form such as `nvapi...1234`);
  - included in AI conversation messages, prompts, or logs;
  - accessible to student code (see the sandbox section below).
- It is only ever sent to the provider base URL that you configured, over
  HTTPS.

## The execution sandbox

Student code is never executed inside the web server process. Every run is a
**separate OS process** launched by `backend/app/services/execution.py`:

| Control | Implementation |
| --- | --- |
| Process isolation | `python -I -S backend/app/runner/run_student.py <code>` - isolated mode, no site-packages |
| Environment stripped | Only `PATH` + `SystemRoot`-class minimal vars are passed; your API key is not in the child's environment (tested) |
| Working directory | A fresh `data/exec_tmp/run_*` folder per run, deleted afterwards |
| Timeout | Hard wall-clock timeout (10s default, max 20s); the child is killed and the result reports `timed_out` |
| Memory | 256 MB cap via Windows **Job Object** (`SetInformationJobObject`) or POSIX `rlimit` |
| Network | `socket`, `ssl`, `urllib`, `requests`, `httpx`, `aiohttp`, `ftp/smtp/poplib`, `webbrowser` imports are blocked by an import hook (tested) |
| Process spawning | `subprocess`, `ctypes`, `multiprocessing`, and `os.system`/`os.popen`/`exec*`/`spawn*`/`fork` are blocked (tested) |
| Filesystem writes | `open(...)` write modes and `os` write ops are restricted to the scratch dir; everything else raises `PermissionError` (tested) |
| Concurrency | A semaphore (3) caps parallel runs; the HTTP layer adds a 40/min rate limit |

### Honest threat model

This sandbox is designed for its actual setting: a **local, single-user
learning tool where the user is running their own code**. Against that threat
model it is strong: untrusted network access from exercises is prevented,
file damage is contained to a temp folder, runaway programs are killed, and
secrets are out of reach.

It is **not** a hardened multi-tenant sandbox. A determined local attacker
with your own credentials could in principle escape some layers (for example
by patching the runner source on disk). Do **not** run this service exposed
to untrusted networks. If you ever deploy it that way:

1. run it inside a dedicated container/VM per execution,
2. put authentication on every endpoint (the API is already structured with a
   `user_id` boundary - see `get_user` usage in the routers),
3. terminate TLS at a reverse proxy,
4. replace the in-memory limiter with a shared store (e.g. Redis).

## Other protections

- **Grading never trusts the AI**: known-answer exercises and code tests are
  graded deterministically server-side. Answers, hints and solutions are never
  included in API responses before they are earned (`sanitize_exercise()` in
  `schemas.py`).
- **Request limits**: bodies over 1.5 MB are rejected with 413; a shared
  in-memory sliding-window limiter guards the expensive endpoints (AI 20/min,
  provider tests 10/min, execution 40/min).
- **Structured errors**: the API returns `{"error": {"code", "message"}}`
  shapes; unexpected 500s never leak stack traces to the browser.
- **Secrets in git**: `.gitignore` excludes `.env`, `data/`, `node_modules/`,
  and build output. `.env.example` contains placeholders only.
