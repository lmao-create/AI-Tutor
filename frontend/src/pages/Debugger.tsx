import { useState } from "react";
import { Link } from "react-router-dom";
import { streamSse } from "../api/client";
import { CodeEditor } from "../components/CodeEditor";
import { Markdown } from "../components/Markdown";
import { Button, Card, Label, useToast } from "../components/ui";

const SAMPLE_CODE = `def average(numbers):
    total = 0
    for n in numbers:
        total += n
    return total / len(total)`;

const SAMPLE_ERROR = `TypeError: unsupported operand type(s) for /: 'int' and 'int'`;

export default function Debugger() {
  const [code, setCode] = useState(SAMPLE_CODE);
  const [errorMessage, setErrorMessage] = useState(SAMPLE_ERROR);
  const [expected, setExpected] = useState("");
  const [actual, setActual] = useState("");
  const [result, setResult] = useState("");
  const [running, setRunning] = useState(false);
  const [failed, setFailed] = useState(false);
  const { toast } = useToast();

  async function run() {
    setRunning(true);
    setResult("");
    setFailed(false);
    await streamSse(
      "/tools/debug",
      {
        code,
        error_message: errorMessage,
        expected,
        actual,
      },
      {
        onDelta: (piece) => setResult((r) => r + piece),
        onError: (_code, message) => {
          setFailed(true);
          setResult(message);
        },
      },
    );
    setRunning(false);
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          AI Debugging Assistant
        </h1>
        <p className="mt-1 text-sm text-muted">
          Describe the bug precisely and the tutor will diagnose the cause,
          teach the concept, point at the offending line, and suggest a minimal
          fix. It never claims your code was run unless it actually ran it.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div>
            <Label>Your code</Label>
            <CodeEditor
              value={code}
              onChange={setCode}
              language="python"
              height="220px"
              fontSize={13}
            />
          </div>
          <div>
            <Label htmlFor="err">Error / traceback (paste exactly)</Label>
            <textarea
              id="err"
              className="input-base h-24 font-mono text-xs"
              value={errorMessage}
              onChange={(e) => setErrorMessage(e.target.value)}
              placeholder="Traceback (most recent call last): ..."
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="exp">Expected behavior</Label>
              <input
                id="exp"
                className="input-base"
                value={expected}
                onChange={(e) => setExpected(e.target.value)}
                placeholder="What should happen?"
              />
            </div>
            <div>
              <Label htmlFor="act">Actual behavior</Label>
              <input
                id="act"
                className="input-base"
                value={actual}
                onChange={(e) => setActual(e.target.value)}
                placeholder="What happens instead?"
              />
            </div>
          </div>
          <Button onClick={run} disabled={running}>
            {running ? "Diagnosing..." : "Diagnose my bug"}
          </Button>
        </div>

        <div>
          <Label>Diagnosis (AI-generated - verify before trusting)</Label>
          <Card className="min-h-[calc(100%-1.5rem)] overflow-y-auto p-4">
            {result ? (
              <>
                <Markdown content={result} />
                <div className="mt-3 border-t border-border pt-2 text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      navigator.clipboard.writeText(result).then(
                        () => toast("Diagnosis copied to clipboard.", "success"),
                        () => toast("Clipboard was blocked.", "danger"),
                      )
                    }
                  >
                    Copy diagnosis
                  </Button>
                </div>
              </>
            ) : running ? (
              <p className="text-sm text-muted">Reading the traceback...</p>
            ) : failed ? (
              <p className="text-sm text-danger">Could not diagnose.</p>
            ) : (
              <p className="text-sm text-muted">
                Paste the failing code, the exact error text, and what you
                expected. Precision from you means precision from the tutor.
              </p>
            )}
          </Card>
        </div>
      </div>

      <p className="text-xs text-muted">
        Tip: run the code in the{" "}
        <Link to="/playground" className="text-primary hover:underline">
          Playground
        </Link>{" "}
        first - a fresh, exact traceback makes diagnosis far more reliable.
      </p>
    </div>
  );
}
