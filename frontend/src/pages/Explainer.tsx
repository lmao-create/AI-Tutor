import { useState } from "react";
import { Link } from "react-router-dom";
import { streamSse } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { ExplainMode } from "../api/types";
import { CodeEditor } from "../components/CodeEditor";
import { Markdown } from "../components/Markdown";
import { Button, Card, Label, Select, useToast } from "../components/ui";

const SAMPLE = `def find_duplicates(items):
    seen = []
    dupes = []
    for item in items:
        if item in seen and item not in dupes:
            dupes.append(item)
        seen.append(item)
    return dupes

print(find_duplicates([1, 2, 3, 2, 1]))`;

export default function Explainer() {
  const { data: modesData } = useApi<{ modes: ExplainMode[] }>(
    "/tools/explain/modes",
  );
  const modes = modesData?.modes ?? [];

  const [code, setCode] = useState(SAMPLE);
  const [codeB, setCodeB] = useState("");
  const [mode, setMode] = useState("explain");
  const [language, setLanguage] = useState("python");
  const [result, setResult] = useState("");
  const [running, setRunning] = useState(false);
  const [failed, setFailed] = useState(false);
  const { toast } = useToast();

  async function run() {
    setRunning(true);
    setResult("");
    setFailed(false);
    await streamSse(
      "/tools/explain",
      { code, language, mode, code_b: codeB || null },
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

  const isCompare = mode === "compare";

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          AI Code Explainer
        </h1>
        <p className="mt-1 text-sm text-muted">
          Paste any code and choose how it should be explained. Your original
          code is preserved unchanged - suggestions are shown separately, and
          every result is labeled as AI-generated.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        <Select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="w-auto min-w-56"
          aria-label="Explanation mode"
        >
          {modes.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </Select>
        <Select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="w-auto"
          aria-label="Language"
        >
          {["python", "javascript", "html", "css"].map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </Select>
        <Button onClick={run} disabled={running || !code.trim()}>
          {running ? "Working..." : "Explain"}
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div>
            <Label>Your code</Label>
            <CodeEditor
              value={code}
              onChange={setCode}
              language={language}
              height="260px"
              fontSize={13}
            />
          </div>
          {isCompare && (
            <div>
              <Label>Implementation B</Label>
              <CodeEditor
                value={codeB}
                onChange={setCodeB}
                language={language}
                height="180px"
                fontSize={13}
              />
            </div>
          )}
        </div>

        <div>
          <Label>Explanation (AI-generated - always verify)</Label>
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
                        () => toast("Result copied to clipboard.", "success"),
                        () => toast("Clipboard was blocked.", "danger"),
                      )
                    }
                  >
                    Copy result
                  </Button>
                </div>
              </>
            ) : running ? (
              <p className="text-sm text-muted">Generating...</p>
            ) : failed ? (
              <p className="text-sm text-danger">Could not generate an explanation.</p>
            ) : (
              <p className="text-sm text-muted">
                Choose a mode above and press Explain. Suggestions from the AI
                are teaching aids - they are never a substitute for running and
                testing your own code.
              </p>
            )}
          </Card>
        </div>
      </div>

      {!modes.length && (
        <p className="text-xs text-muted">
          Could not load explanation modes - is the backend running?{" "}
          <Link to="/" className="text-primary hover:underline">
            Reload the app
          </Link>
          .
        </p>
      )}
    </div>
  );
}
