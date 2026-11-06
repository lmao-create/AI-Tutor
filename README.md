# CodeTutor AI

An AI-powered programming tutor that actually **teaches**: short lessons, real
exercises, honest feedback on your code, and a patient assistant that adapts
to your level. Everything works offline out of the box; add any
OpenAI-compatible AI provider (NVIDIA NIM, OpenAI, Groq, OpenRouter, Ollama...)
to unlock the AI features.

```
┌──────────────────────────────┐        ┌────────────────────────────┐
│  Frontend: React + TS + Vite │  /api  │  Backend: FastAPI + SQLite │
│  Monaco editor, Tailwind     │ ─────► │  AI client, sandbox exec,  │
│  (dev server on :5173)       │  proxy │  deterministic grader      │
└──────────────────────────────┘        └─────────────┬──────────────┘
                                          sandboxed   │  subprocess
                                          child       ▼
                                     ┌────────────────────────────┐
                                     │  run_student.py (isolated: │
                                     │  no network, no secrets,   │
                                     │  time + memory limits)     │
                                     └────────────────────────────┘
```

---

## Quick start (Windows)

```bat
start.bat
```

That's it. The script:

1. Creates `backend\.venv` and installs Python dependencies (first run only).
2. Installs frontend npm dependencies (first run only).
3. Starts the API server on **http://127.0.0.1:8123** (seeds the SQLite
   database with the full Python course on first run).
4. Starts the frontend on **http://localhost:5173** and opens it in your
   browser.

Other entry points:

```bat
run_tests.bat              REM run the full test suite (87 tests)
start.bat -Prod            REM build once, serve everything from :8123
start.ps1 -RunTests        REM tests only (PowerShell)
```

### Requirements

- **Windows 10/11** (also runs on macOS/Linux - use `start.ps1` steps manually)
- **Python 3.10+** (developed and tested on 3.13)
- **Node.js 18+** (tested on 24)

No cloud account is required. The application runs fully local; the only
optional external service is an AI provider you configure yourself.

---

## Using the app

| Area | What it does |
| --- | --- |
| **Dashboard** | Real persisted progress: streak, lessons done, recommended next lesson |
| **Learn** | The 22-lesson Python course: explanations, runnable examples, quizzes, exercises with progressive hints |
| **Practice** | 34 exercises across 5 kinds (MCQ, predict-output, fill-in-blank, find-the-bug, write-a-program) with deterministic grading |
| **AI Tutor** | Chat with a patient teacher in 6 modes (Learn / Practice / Debug / Project / Interview / Explain). Streaming responses, stop, retry, history |
| **Playground** | Write and run Python in an isolated sandbox: stdin, error reporting, 10s timeout |
| **Explainer** | 11 explanation modes: explain, line-by-line, beginner, find-bugs, improvements, algorithm, complexity, pseudocode, comments, refactor, compare |
| **Debugger** | Structured diagnosis from your code + error + expected/actual behavior |
| **Projects** | 9 guided projects with milestone-by-milestone guidance (never dumping full solutions) |
| **Progress** | Everything an LMS would claim to show, computed from real data: strengths, weaknesses, achievements, streak |
| **Settings** | Provider configuration + connection test; preferences |

---

## Configuring an AI provider (example: NVIDIA NIM)

1. Create a free key at <https://build.nvidia.com> (Sign in → your model →
   *Generate API key*).
2. Open **Settings** in the app, click the *NVIDIA NIM* preset, paste the key,
   click **Save configuration**, then **Test connection**.
3. Pick any NVIDIA model id, e.g. `meta/llama-3.3-70b-instruct`.

The key is stored **only on the backend** in `data/secrets.json` (gitignored,
user-only permissions). It is never returned to the browser in any API
response - the UI only ever shows a masked form like `nvapi...1234`.

Other supported providers (all OpenAI-compatible, no code changes needed):

| Provider | Base URL | Example model |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `meta/llama-3.3-70b-instruct` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` |
| Ollama (local) | `http://127.0.0.1:11434/v1` | `llama3.1` |

Or set it in the environment (see `.env.example`):

```bat
copy .env.example .env
notepad .env
```

Environment variables are used as a fallback when no provider is saved in
Settings. **Never commit `.env`** - it is gitignored.

### Without any provider ("demo mode")

Running with no API key is a fully-labelled demo mode: the AI tutor, explainer
and debugger are disabled with clear instructions to add a provider, while
**all lessons, exercises, quizzes, the playground, projects and progress
tracking work offline**. The app never fakes an AI response to pretend a
provider exists.

---

## Code execution safety

Student code is **never executed inside the web server**. Each run:

- spawns a **separate process** (`python -I -S run_student.py`) with
- a **stripped environment** (only `PATH`/`SystemRoot`-class minimal vars - your
  API key is never in scope),
- a **fresh scratch working directory**, deleted after the run,
- a **hard wall-clock timeout** (10s default, 20s max),
- a **memory cap** of 256 MB (Windows Job Object / POSIX `rlimit`),
- and an in-process wrapper that **blocks network modules** (`socket`, `urllib`,
  `requests`, `ctypes`, `subprocess`, ...), disables `os.system`/`os.popen`/
  process-spawning, and constrains file writes to the scratch folder.

Only Python is offered for execution, because only Python has a working
sandbox path here. Other languages are not listed as available - the app does
not claim capabilities it lacks. Read [`docs/SECURITY.md`](docs/SECURITY.md)
for the honest threat model (local, single-user tool - not a hardened
multi-tenant sandbox).

---

## Project layout

```
AI Tutor/
├── start.bat                  double-click launcher
├── run_tests.bat              test runner
├── start.ps1                  the real startup logic
├── .env.example               provider config template (no real keys)
├── backend/
│   ├── requirements.txt       fastapi, uvicorn, httpx, python-dotenv, pydantic
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py            app factory, middleware, exception handling
│   │   ├── config.py          settings (env vars)
│   │   ├── db.py + migrations.py   SQLite, WAL, versioned migrations
│   │   ├── seed.py            idempotent content loader
│   │   ├── schemas.py         pydantic request models + answer sanitizers
│   │   ├── errors.py, ratelimit.py, secrets.py
│   │   ├── content/           courses, 22 lessons, exercises, projects (JSON)
│   │   ├── runner/run_student.py   the sandbox child
│   │   ├── services/          ai.py, tutor.py, execution.py, grader.py,
│   │   │                      progress.py
│   │   └── routers/           health, settings, conversations, courses,
│   │                          exercises, execution, tools, progress, projects
│   └── tests/                 87 tests (pytest)
├── frontend/
│   ├── src/                   React 18 + TS + Tailwind + Monaco
│   │   ├── pages/             Dashboard, Learn, LessonPage, Practice, Tutor,
│   │   │                      Playground, Explainer, Debugger, Projects,
│   │   │                      ProjectPage, Progress, Settings
│   │   ├── components/        ui kit, Layout, Markdown, CodeEditor, Quiz,
│   │   │                      ExercisePanel, DemoBanner
│   │   ├── api/               typed client + SSE stream consumer
│   │   └── lib/ lib/hooks/    theme, utils, data hooks
│   └── vite.config.ts         /api proxy to the backend (keeps SSE intact)
└── docs/
    ├── SECURITY.md            sandbox + secrets honesty
    └── ADDING_COURSES.md      how to extend the course content
```

The SQLite database and local data live in `data/` (gitignored). **Delete
`data/` to fully reset the app** (content is re-seeded on next boot; API keys
are in `data/secrets.json`, so this removes them too).

---

## Testing

```bat
run_tests.bat
```

87 tests covering:

- **Database** - migrations idempotent, JSON decoding, transactions, FKs
- **Courses** - retrieval, planned-course honesty, quiz answers never leaked
- **Grading** - all five exercise kinds, determinism, timeouts, student errors
- **Execution** - stdout/stdin, timeout kill, syntax errors, network blocked,
  write-outside-scratch blocked, environment stripped, output truncation
- **Progress** - streaks, achievements, reset (all from real data)
- **Provider** - config round-trip, masking, connection tests with a mocked
  transport, streaming happy path, HTTP error mapping (401/402/404/429/5xx),
  network failures, malformed SSE
- **API** - conversations CRUD, chat SSE wiring with a mocked provider, demo
  mode refusals, validation errors, rate limits, body-size limits

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `npm warn install-scripts` for esbuild | Run `node frontend\node_modules\esbuild\install.js` (start.ps1 does this for you). |
| Port 8123 or 5173 already in use | Another app holds it: set `CODETUTOR_PORT` in `.env` for the API, `--port` for Vite. (`8000` is commonly taken on Windows.) |
| `python --version` not found | Reinstall Python from python.org and tick **Add Python to PATH**. |
| App stuck at "Checking provider..." | The API isn't up - watch the start.ps1 output; start the backend manually: `cd backend; .venv\Scripts\python -m uvicorn app.main:app --port 8123`. |
| AI says "no provider configured" | Add a key in Settings, then **Test connection** (a wrong base URL / model fails here with the provider's reason). |
| Code runs forever | It won't: the sandbox kills execution at 10s and reports a clean timeout. |
| First launch is slow | One-time dependency install; subsequent starts take seconds. |

---

## Known limitations (honest list)

- Only the **Python** learning path has lessons today. The other nine courses
  are listed as *in development* and never claim finished lessons they do not
  have. Add content via `app/content/*.json` (see
  [`docs/ADDING_COURSES.md`](docs/ADDING_COURSES.md)).
- **Python is the only executable language** - other languages deliberately
  stay hidden from the language picker instead of pretending to run.
- Learning time tracking measures *lesson open→complete* time, not attention.
- The AI tutor has no server-side memory of lessons it has taught; personalization
  comes from your real progress data, which is injected into each prompt.
- The sandbox is a strong *local* sandbox, not a hardened cloud service
  (see `docs/SECURITY.md`). If you ever deploy this publicly, swap
  `services/execution.py` for a real container sandbox and add authentication.
