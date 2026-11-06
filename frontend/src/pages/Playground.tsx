import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { ExecResult, LanguageInfo } from "../api/types";
import { CodeEditor } from "../components/CodeEditor";
import { Button, Card, Label, Textarea, useToast } from "../components/ui";

const STARTER = `# Welcome to the CodeTutor playground!
# Write Python here and press Run - your code executes in an
# isolated sandbox: no network, no secrets, hard 10s time limit.

name = input()
print("Hello, " + name + "!")
`;

const SAMPLES: { title: string; code: string }[] = [
  {
    title: "Variables and math",
    code: `a = 7\nb = 3\nprint("Sum:", a + b)\nprint("Modulo:", a % b)\nprint("Power:", a ** b)`,
  },
  {
    title: "Loops",
    code: `total = 0\nfor n in range(1, 11):\n    total += n\nprint("Sum 1..10:", total)`,
  },
  {
    title: "Lists",
    code: `names = ["Ada", "Grace", "Alan"]\nnames.append("Margaret")\nfor i, name in enumerate(names, 1):\n    print(i, name)`,
  },
  {
    title: "Functions",
    code: `def greet(name, greeting="Hello"):\n    return f"{greeting}, {name}!"\n\nprint(greet("Ada"))\nprint(greet("Grace", "Hi"))`,
  },
];

export default function Playground() {
  const location = useLocation();
  const navigate = useNavigate();
  const stateCode = (location.state as { code?: string } | null)?.code;
  const [code, setCode] = useState(stateCode ?? STARTER);
  const [stdin, setStdin] = useState("");
  const [result, setResult] = useState<ExecResult | null>(null);
  const [running, setRunning] = useState(false);
  const { data: langs } = useApi<{ languages: LanguageInfo[] }>(
    "/execution/languages",
  );
  const { toast } = useToast();
  const consumedPrefill = useRef(false);

  useEffect(() => {
    // Prefilled from "Open in playground" on a lesson page.
    if (stateCode && !consumedPrefill.current) {
      consumedPrefill.current = true;
      setCode(stateCode);
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [stateCode, navigate, location.pathname]);

  async function run() {
    setRunning(true);
    setResult(null);
    try {
      const res = await api.post<ExecResult>("/execution/run", {
        language: "python",
        code,
        stdin,
      });
      setResult(res);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Run failed.", "danger");
    } finally {
      setRunning(false);
    }
  }

  function reset() {
    setCode(STARTER);
    setStdin("");
    setResult(null);
  }

  const lang = langs?.languages.find((l) => l.id === "python");
  const otherLangs = (langs?.languages ?? []).filter((l) => !l.executable);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Code Playground
          </h1>
          <p className="mt-1 text-sm text-muted">
            Write, run and break Python safely. Your code runs in an isolated
            sandbox process - no network, no access to this app's secrets, and
            a hard time limit.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={reset} disabled={running}>
            Reset
          </Button>
          <Button onClick={run} disabled={running}>
            {running ? "Running..." : "▶ Run"}
          </Button>
        </div>
      </header>

      {lang && (
        <p className="text-xs text-muted">
          Executing with Python {lang.version} · timeout {lang.timeout_seconds}s
          · memory and CPU limited
          {otherLangs.length > 0 &&
            ` · other languages (${otherLangs.map((l) => l.label).join(", ")}) are not executable yet - we only list languages whose execution is genuinely available.`}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <Button
            key={s.title}
            variant="ghost"
            size="sm"
            onClick={() => setCode(s.code)}
          >
            {s.title}
          </Button>
        ))}
      </div>

      <CodeEditor
        value={code}
        onChange={setCode}
        language="python"
        height="300px"
        fontSize={14}
      />

      <div>
        <Label htmlFor="stdin">Program input (stdin)</Label>
        <Textarea
          id="stdin"
          rows={2}
          className="font-mono text-xs"
          placeholder="Whatever the program reads via input() - one line per answer."
          value={stdin}
          onChange={(e) => setStdin(e.target.value)}
        />
      </div>

      <Card className="space-y-2">
        <h2 className="text-sm font-semibold">Output</h2>
        {result ? (
          <>
            <div className="flex items-center gap-3 text-xs text-muted">
              <span>
                {result.timed_out
                  ? "⏱ Timed out"
                  : result.exit_code === 0
                    ? "✓ Finished"
                    : `✗ Exited with ${result.exit_code}`}
              </span>
              <span>{result.duration_ms} ms</span>
              {result.truncated && <span>(output truncated)</span>}
            </div>
            <pre className="mt-1 min-h-8 overflow-x-auto whitespace-pre-wrap rounded-lg bg-bg p-3 text-sm">
              {result.stdout || (result.exit_code === 0 ? "(no output)" : "")}
            </pre>
            {result.stderr && (
              <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-danger/5 p-3 text-xs text-danger">
                {result.stderr.slice(0, 2000)}
              </pre>
            )}
            {result.error_info && (
              <p className="text-xs text-danger">
                {result.error_info.type}
                {result.error_info.line
                  ? ` on line ${result.error_info.line}`
                  : ""}
                : {result.error_info.message}
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-muted">
            Press Run to see your program's output here.
          </p>
        )}
      </Card>
    </div>
  );
}
