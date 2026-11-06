import { useState } from "react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { Exercise } from "../api/types";
import { ExercisePanel } from "../components/ExercisePanel";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Select,
  Skeleton,
} from "../components/ui";
import { cx } from "../lib/utils";

const KIND_OPTIONS = [
  { value: "", label: "All types" },
  { value: "mcq", label: "Multiple choice" },
  { value: "predict_output", label: "Predict the output" },
  { value: "fill_blank", label: "Fill in the blank" },
  { value: "find_bug", label: "Find the bug" },
  { value: "write_program", label: "Write a program" },
];

const KIND_BADGE: Record<string, string> = {
  mcq: "Multiple choice",
  predict_output: "Predict output",
  fill_blank: "Fill in the blank",
  find_bug: "Find the bug",
  write_program: "Write a program",
};

export default function Practice() {
  const [kind, setKind] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const query =
    "?course=python" +
    (kind ? `&kind=${kind}` : "") +
    (difficulty ? `&difficulty=${difficulty}` : "");
  const { data, error, loading, refresh } = useApi<{ exercises: Exercise[] }>(
    `/exercises${query}`,
  );

  const [selected, setSelected] = useState<Exercise | null>(null);

  async function openExercise(ex: Exercise) {
    setSelectedId(ex.id);
    try {
      // Fetch the detailed row (includes this learner's status).
      const full = await api.get<Exercise>(`/exercises/${ex.id}`);
      setSelected(full);
    } catch {
      setSelected(null);
    }
  }

  if (loading && !data) return <Skeleton className="h-64" />;
  if (error) return <ErrorState error={error} />;

  const exercises = data?.exercises ?? [];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Practice</h1>
        <p className="mt-1 text-sm text-muted">
          Every exercise is graded deterministically - no AI guessing. Wrong
          answers stay private and correct answers are revealed only after you
          earn them.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        <Select
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setSelected(null);
          }}
          className="w-auto"
          aria-label="Filter by exercise type"
        >
          {KIND_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
        <Select
          value={difficulty}
          onChange={(e) => {
            setDifficulty(e.target.value);
            setSelected(null);
          }}
          className="w-auto"
          aria-label="Filter by difficulty"
        >
          <option value="">All difficulties</option>
          <option value="1">1 - warm-up</option>
          <option value="2">2 - core</option>
          <option value="3">3 - challenge</option>
        </Select>
        <span className="self-center text-xs text-muted">
          {exercises.length} exercise{exercises.length === 1 ? "" : "s"}
        </span>
      </div>

      {selected ? (
        <Card className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">{selected.title}</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelected(null);
                refresh();
              }}
            >
              ← Back to list
            </Button>
          </div>
          <ExercisePanel
            exercise={selected}
            onStatusChange={() => {
              refresh();
              api
                .get<Exercise>(`/exercises/${selected.id}`)
                .then(setSelected)
                .catch(() => undefined);
            }}
          />
        </Card>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
          {exercises.map((ex) => (
            <li key={ex.id}>
              <button
                onClick={() => openExercise(ex)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surfaceHover"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">
                    {ex.title}
                  </span>
                  <span className="block truncate text-xs text-muted">
                    {ex.prompt.split("\n")[0]}
                  </span>
                </span>
                <Badge>{KIND_BADGE[ex.kind] ?? ex.kind}</Badge>
                <span
                  className={cx(
                    "shrink-0 text-xs",
                    ex.status?.passed ? "text-success" : "text-muted",
                  )}
                >
                  {ex.status?.passed
                    ? "passed"
                    : ex.status && ex.status.attempts > 0
                      ? "tried"
                      : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {!selected && exercises.length === 0 && !loading && (
        <EmptyState
          title="No exercises match those filters"
          description="Try widening the filters to see all practice exercises."
        />
      )}
    </div>
  );
}
