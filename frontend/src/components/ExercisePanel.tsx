import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  ExecResult,
  Exercise,
  HintResponse,
  SubmitResult,
} from "../api/types";
import { CodeEditor } from "./CodeEditor";
import { Markdown } from "./Markdown";
import { Button, Modal, Spinner, useToast } from "./ui";
import { cx } from "../lib/utils";

interface ExercisePanelProps {
  exercise: Exercise;
  onStatusChange?: () => void;
}

const KIND_LABELS: Record<string, string> = {
  mcq: "Multiple choice",
  predict_output: "Predict the output",
  fill_blank: "Fill in the blank",
  find_bug: "Find the bug",
  write_program: "Write a program",
};

export function ExercisePanel({
  exercise,
  onStatusChange,
}: ExercisePanelProps) {
  const isCode = exercise.kind === "write_program";
  const [code, setCode] = useState(exercise.starter_code ?? "");
  const [choice, setChoice] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [line, setLine] = useState("");

  const [runResult, setRunResult] = useState<ExecResult | null>(null);
  const [running, setRunning] = useState(false);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [hints, setHints] = useState<string[]>([]);
  const [hintLevel, setHintLevel] = useState(0);
  const [solutionCode, setSolutionCode] = useState("");
  const [solutionNote, setSolutionNote] = useState("");
  const [solutionOpen, setSolutionOpen] = useState(false);
  const [loadingHint, setLoadingHint] = useState(false);

  const status = exercise.status;
  const maxHints = exercise.hint_count;
  const { toast } = useToast();

  async function runCode() {
    setRunning(true);
    setRunResult(null);
    try {
      const res = await api.post<ExecResult>("/execution/run", {
        language: "python",
        code,
        stdin: "",
      });
      setRunResult(res);
      onStatusChange?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Run failed.", "danger");
    } finally {
      setRunning(false);
    }
  }

  async function submit() {
    setSubmitting(true);
    try {
      const body = isCode
        ? { code }
        : exercise.kind === "mcq"
          ? { choice }
          : exercise.kind === "predict_output"
            ? { output: text }
            : exercise.kind === "find_bug"
              ? { line: Number(line) }
              : { text };
      const res = await api.post<SubmitResult>(
        `/exercises/${exercise.id}/submit`,
        body,
      );
      setSubmitResult(res);
      if (res.passed) toast("Exercise passed!", "success");
      onStatusChange?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Submit failed.", "danger");
    } finally {
      setSubmitting(false);
    }
  }

  async function requestHint() {
    setLoadingHint(true);
    try {
      const res = await api.post<HintResponse>(`/exercises/${exercise.id}/hint`);
      if (res.type === "hint") {
        setHints((h) => [...h, res.content ?? ""]);
        setHintLevel(res.level);
      } else {
        // The solution is the automatic next step once all hints are used.
        const sol = await api.get<{ code: string; explanation: string }>(
          `/exercises/${exercise.id}/solution`,
        );
        setSolutionCode(sol.code ?? "");
        setSolutionNote(
          sol.explanation ||
            "(This exercise has no separate explanation - review the hints " +
            "and the correct answer above.)",
        );
        setSolutionOpen(true);
        setHintLevel(res.level);
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Hint failed.", "danger");
    } finally {
      setLoadingHint(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-xs text-muted">
        <Badge tone="primary">{KIND_LABELS[exercise.kind] ?? exercise.kind}</Badge>
        <span>Difficulty {exercise.difficulty}/3</span>
        {status?.passed && <Badge tone="success">Passed</Badge>}
        {status && status.attempts > 0 && !status.passed && (
          <span>
            {status.attempts} attempt{status.attempts === 1 ? "" : "s"} so far
          </span>
        )}
      </div>

      <Markdown content={exercise.prompt} />

      {isCode ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted">
              Your solution (Python)
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCode(exercise.starter_code ?? "")}
              >
                Reset
              </Button>
              <Button variant="outline" size="sm" onClick={runCode}
                disabled={running}>
                {running ? "Running..." : "Run"}
              </Button>
            </div>
          </div>
          <CodeEditor
            value={code}
            onChange={setCode}
            language="python"
            height="220px"
            fontSize={13}
          />
        </div>
      ) : (
        <AnswerInput
          kind={exercise.kind}
          options={exercise.options}
          choice={choice}
          setChoice={setChoice}
          text={text}
          setText={setText}
          line={line}
          setLine={setLine}
        />
      )}

      {runResult && <RunOutput result={runResult} />}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={submit} disabled={submitting} size="sm">
          {submitting ? "Grading..." : "Submit answer"}
        </Button>
        <Button variant="outline" size="sm" onClick={requestHint}
          disabled={loadingHint}>
          {loadingHint
            ? "Loading..."
            : hintLevel < maxHints
              ? `Hint ${hintLevel + 1} of ${maxHints}`
              : "Show explained solution"}
        </Button>
        {status?.passed && (
          <span className="text-xs text-success">
            Passed - try the next exercise below the lesson.
          </span>
        )}
      </div>

      {submitResult && (
        <div
          className={cx(
            "rounded-lg border p-4 text-sm",
            submitResult.passed
              ? "border-success/40 bg-success/5"
              : "border-warning/40 bg-warning/5",
          )}
        >
          <p className="font-medium">
            {submitResult.passed
              ? "Correct!"
              : "Not yet - keep going, mistakes are how learning happens."}
          </p>
          <p className="mt-1 text-muted">{submitResult.feedback.message}</p>
          {submitResult.feedback.tests && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr>
                    <th className="border border-border px-2 py-1 text-left">
                      Test
                    </th>
                    <th className="border border-border px-2 py-1 text-left">
                      Result
                    </th>
                    <th className="border border-border px-2 py-1 text-left">
                      Details
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {submitResult.feedback.tests.map((t, i) => (
                    <tr key={i}>
                      <td className="border border-border px-2 py-1">
                        {t.call ?? `Case ${t.case ?? i + 1}`}
                      </td>
                      <td
                        className={cx(
                          "border border-border px-2 py-1 font-medium",
                          t.ok ? "text-success" : "text-danger",
                        )}
                      >
                        {t.ok ? "pass" : "fail"}
                      </td>
                      <td className="border border-border px-2 py-1 text-muted">
                        {t.error
                          ? t.error
                          : t.got !== undefined
                            ? `got ${t.got} / expected ${t.expected}`
                            : t.expected
                              ? `expected: ${t.expected}`
                              : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {submitResult.run?.error_info && (
            <p className="mt-2 text-xs text-danger">
              {submitResult.run.error_info.type}
              {submitResult.run.error_info.line
                ? ` (line ${submitResult.run.error_info.line})`
                : ""}
              : {submitResult.run.error_info.message}
            </p>
          )}
          {submitResult.explanation && (
            <div className="mt-3 border-t border-border pt-2">
              <p className="text-xs font-semibold text-primary">
                The correct approach
              </p>
              <Markdown content={submitResult.explanation} />
            </div>
          )}
          {!submitResult.passed && (
            <>
              {hintLevel === 0 && (
                <p className="mt-2 text-xs text-muted">
                  Stuck? Press <span className="font-medium">Hint</span> -
                  hints come one at a time and the solution only appears after
                  you have used them.
                </p>
              )}
              <p className="mt-2 text-xs text-muted">
                Want to talk it through?{" "}
                <Link
                  to={`/tutor?exercise=${exercise.id}`}
                  className="text-primary underline"
                >
                  Ask the AI tutor
                </Link>
                .
              </p>
            </>
          )}
        </div>
      )}

      {hints.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-primary">Hints</p>
          {hints.map((h, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-surface p-3 text-sm text-muted"
            >
              {h}
            </div>
          ))}
        </div>
      )}

      <Modal
        open={solutionOpen}
        title="Explained solution"
        onClose={() => setSolutionOpen(false)}
      >
        <p className="mb-2 text-xs">
          This is the reference solution. Study it, then hide it and write the
          code yourself from scratch - that is what makes it stick.
        </p>
        {solutionCode ? (
          <>
            <Markdown content={"```python\n" + solutionCode + "\n```"} />
            <Markdown content={solutionNote} />
          </>
        ) : (
          <>
            <p className="text-xs text-muted">
              This is a conceptual exercise - there is no reference code. Read
              the correct approach below.
            </p>
            <Markdown content={solutionNote} />
          </>
        )}
        <div className="mt-4 flex justify-end">
          <Button size="sm" onClick={() => setSolutionOpen(false)}>
            Got it, close
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function Badge({
  tone,
  children,
}: {
  tone: "primary" | "success" | "warning" | "danger" | "muted";
  children: React.ReactNode;
}) {
  const tones: Record<string, string> = {
    primary: "border-primary/50 text-primary",
    success: "border-success/40 text-success",
    warning: "border-warning/40 text-warning",
    danger: "border-danger/40 text-danger",
    muted: "border-muted/30 text-muted",
  };
  return (
    <span
      className={cx(
        "rounded-full border px-2 py-0.5 text-xs font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

function AnswerInput({
  kind,
  options,
  choice,
  setChoice,
  text,
  setText,
  line,
  setLine,
}: {
  kind: string;
  options?: string[] | null;
  choice: number | null;
  setChoice: (n: number) => void;
  text: string;
  setText: (s: string) => void;
  line: string;
  setLine: (s: string) => void;
}) {
  if (kind === "mcq") {
    if (!options || options.length === 0) {
      return (
        <p className="text-sm text-muted">
          Answer using the options in the prompt above.
        </p>
      );
    }
    return (
      <div className="space-y-1.5">
        {options.map((opt, oi) => (
          <label
            key={oi}
            className={[
              "flex cursor-pointer items-start rounded-lg border border-border px-3 py-2 text-sm hover:border-muted/60",
              choice === oi ? "border-primary bg-primary/5" : "",
            ].join(" ")}
          >
            <input
              type="radio"
              name="mcq-choice"
              className="mr-2 mt-0.5"
              checked={choice === oi}
              onChange={() => setChoice(oi)}
            />
            {opt}
          </label>
        ))}
      </div>
    );
  }
  if (kind === "predict_output") {
    return (
      <textarea
        className="input-base font-mono text-xs"
        rows={4}
        placeholder="Type exactly what the program prints, one line per line of output..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
    );
  }
  if (kind === "find_bug") {
    return (
      <input
        className="input-base w-40"
        inputMode="numeric"
        placeholder="Line number"
        value={line}
        onChange={(e) => setLine(e.target.value)}
      />
    );
  }
  return (
    <input
      className="input-base"
      placeholder="Type the missing code"
      value={text}
      onChange={(e) => setText(e.target.value)}
    />
  );
}

function RunOutput({ result }: { result: ExecResult }) {
  return (
    <div className="rounded-lg border border-border bg-bg p-3">
      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          {result.timed_out
            ? "Timed out"
            : result.exit_code === 0
              ? "Finished"
              : `Errored (exit ${result.exit_code})`}
        </span>
        <span>{result.duration_ms} ms</span>
      </div>
      {result.stdout && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-sm text-fg">
          {result.stdout}
        </pre>
      )}
      {result.stderr && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-danger">
          {result.stderr.slice(0, 2000)}
        </pre>
      )}
      {result.error_info && (
        <p className="mt-2 text-xs text-danger">
          {result.error_info.type}
          {result.error_info.line ? ` (line ${result.error_info.line})` : ""}:{" "}
          {result.error_info.message}
        </p>
      )}
    </div>
  );
}
