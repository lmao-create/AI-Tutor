# Adding courses and lessons

All course content lives as JSON files in `backend/app/content/`. The database
is seeded from them **idempotently on every startup** (upserts by natural
keys), so editing content and restarting is the whole workflow - student
progress is preserved because rows are updated in place, never deleted.

## Files

| File | Purpose |
| --- | --- |
| `courses.json` | Course catalog: one entry per path (`status`: `complete` or `planned`) |
| `python_lessons_01.json` … `_07.json` | Lessons for the Python course (glob: `python_lessons_*.json`) |
| `extra_exercises.json` | Practice exercises not tied to a lesson |
| `projects.json` | Guided projects with milestones |

## 1. Add a course entry

In `courses.json`:

```json
{
  "slug": "javascript",
  "title": "JavaScript Fundamentals",
  "description": "The language of the web.",
  "language": "JavaScript",
  "level": "beginner",
  "status": "planned",           // "planned" until the path is complete
  "overview": "One or two sentences.",
  "prerequisites": ["None"],
  "outline": ["Values and variables", "Functions", "DOM"],
  "order_index": 2
}
```

A `planned` course honestly shows *No lessons are available yet* with its
planned topics - never fake lesson pages.

## 2. Add a lessons file

Create `python_lessons_XX.json` (any name matching the glob):

```json
{
  "course_slug": "javascript",
  "lessons": [
    {
      "slug": "first-program",
      "title": "Your First JavaScript Program",
      "summary": "One-line lesson summary shown in the course list.",
      "objectives": ["Explain what a program is", "Run your first statement"],
      "sections": [
        { "heading": "...", "body": "Markdown text ...", "code": "optional code" }
      ],
      "example": {
        "title": "Hello",
        "code": "console.log('Hello!')",
        "explanation": "Markdown, why it works"
      },
      "quiz": [
        {
          "id": "q1",
          "question": "What does this print?",
          "options": ["Hello", "World", "Nothing"],
          "answer": 0,
          "explanation": "Revealed only after the student submits."
        }
      ],
      "exercise": {
        "kind": "mcq",
        "title": "...",
        "prompt": "Markdown prompt",
        "difficulty": 1,
        "answer": {"index": 2},
        "options": ["a", "b", "c"],
        "hints": ["concept", "strategy", "specific clue"],
        "solution": {"code": "", "explanation": "The correct approach"}
      }
    }
  ]
}
```

Lesson order across files is derived from the glob order per file, files in
alphabetical order - keep them numbered.

## 3. Exercise kinds and grading

| `kind` | `answer` | Notes |
| --- | --- | --- |
| `mcq` | `{"index": n}` | `options` field required |
| `predict_output` | `{"output": "..."}` | whitespace-insensitive compare |
| `fill_blank` | `{"text": "..."}` | whitespace-insensitive, case-sensitive |
| `find_bug` | `{"line": n}` | the failing line number |
| `write_program` | none | needs a `test_spec` below |

`write_program` test specs:

```json
"test_spec": {"type": "function", "tests": [
  {"call": "add(2, 3)", "expected": "5"}
]}
```

(or `{"type": "stdout", "cases": [{"stdin": "Ada", "expected_output": "Hi, Ada!"}]}`)

The harness runs your student's code, calls each `call` expression and compares
`repr()` values (with numeric equivalence via literal parsing). Timeouts are
reported as timeouts, exceptions as per-test errors. This is fully
deterministic - the AI never grades code.

## 4. Guided projects

`projects.json` entries have `requirements`, `skills`, `testing_instructions`,
`challenges`, `starter_code`, and a `milestones` array of
`{title, goal, guidance}` where `guidance` is Markdown. Milestones unlock in
order; the UI never reveals later stages early.

## 5. Adding another executable language (Python only today)

Execution requires a real sandbox path:

1. Write a runner script like `backend/app/runner/run_student.py` for the
   language (with the same import/network/filesystem restrictions).
2. Extend `backend/app/services/execution.py` to launch it.
3. Update the `ExecRunIn` schema's `language` literal and the
   `/execution/languages` endpoint.
4. Add tests for timeout, network and output behavior **before** enabling it in
   the UI. Do not add a language until this is genuinely working - the
   Playground only lists languages that truly execute.
