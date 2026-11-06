import { useCallback } from "react";
import Editor, { loader, type OnMount } from "@monaco-editor/react";
import * as monaco from "monaco-editor";

import { useTheme } from "../lib/theme";

// Monaco is bundled locally (no CDN) so the app works offline. Using the
// bundled package also keeps editor behavior consistent and fast.
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

(self as unknown as { MonacoEnvironment?: unknown }).MonacoEnvironment = {
  getWorker: () => new editorWorker(),
};

loader.config({ monaco });

monaco.editor.defineTheme(
  "codetutor-dark",
  {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#0b0f14",
      "editor.foreground": "#e6edf3",
      "editorLineNumber.foreground": "#8b98a5",
      "editorLineNumber.activeForeground": "#e6edf3",
      "editor.selectionBackground": "#3b4368",
      "editor.lineHighlightBackground": "#11161d",
      "editorCursor.foreground": "#6366f1",
      "editorIndentGuide.background": "#1f2933",
    },
  },
);

monaco.editor.defineTheme("codetutor-light", {
  base: "vs",
  inherit: true,
  rules: [],
  colors: {
    "editor.background": "#ffffff",
    "editor.foreground": "#1c2530",
    "editorLineNumber.foreground": "#5c6b7a",
    "editorLineNumber.activeForeground": "#1c2530",
    "editor.selectionBackground": "#c7d2fe",
    "editor.lineHighlightBackground": "#f2f4f7",
    "editorCursor.foreground": "#4f46e5",
  },
});

interface CodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  language?: string;
  height?: string;
  readOnly?: boolean;
  fontSize?: number;
}

function editorHeight(height: string, value: string): string {
  if (height !== "auto") return height;
  const lines = Math.max(3, value.split("\n").length);
  return `${Math.min(560, lines * 20 + 16)}px`;
}

export function CodeEditor({
  value,
  onChange,
  language = "python",
  height = "360px",
  readOnly = false,
  fontSize = 14,
}: CodeEditorProps) {
  const { theme } = useTheme();
  const resolvedHeight = editorHeight(height, value);

  const handleMount = useCallback<OnMount>((editor) => {}, []);

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Editor
        height={resolvedHeight}
        language={language}
        value={value}
        theme={theme === "dark" ? "codetutor-dark" : "codetutor-light"}
        onChange={(v) => onChange?.(v ?? "")}
        onMount={handleMount}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize,
          fontFamily:
            "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          lineNumbers: "on",
          automaticLayout: true,
          scrollBeyondLastLine: false,
          tabSize: 4,
          insertSpaces: true,
          wordWrap: "on",
          scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
          renderLineHighlight: "line",
          smoothScrolling: true,
          overviewRulerLanes: 0,
          lineNumbersMinChars: 4,
        }}
      />
    </div>
  );
}
