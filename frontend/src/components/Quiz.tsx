import { useState } from "react";
import { api } from "../api/client";
import type { QuizResult } from "../api/types";
import { Button } from "./ui";

interface QuizProps {
  lessonId: number;
  questions: { id: string; question: string; options: string[] }[];
  bestScore?: number | null;
  onSubmitted?: () => void;
}

export function Quiz({ lessonId, questions, bestScore, onSubmitted }: QuizProps) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const answered = Object.keys(answers).length === questions.length;

  async function submit() {
    if (!answered) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.post<QuizResult>(
        `/lessons/${lessonId}/quiz`,
        { answers },
      );
      setResult(res);
      onSubmitted?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function retry() {
    setAnswers({});
    setResult(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{questions.length} questions</span>
        {bestScore != null && (
          <>
            <span>·</span>
            <span>Your best: {bestScore}%</span>
          </>
        )}
      </div>

      {questions.map((q, qi) => {
        const chosen = result
          ? result.per_question.find((r) => r.id === q.id)?.chosen ?? null
          : (answers[q.id] ?? null);
        const graded = result?.per_question.find((r) => r.id === q.id);
        return (
          <div
            key={q.id}
            className="rounded-lg border border-border bg-surface p-4"
          >
            <p className="text-sm font-medium">
              {qi + 1}. {q.question}
            </p>
            <div className="mt-2 space-y-1.5">
              {q.options.map((opt, oi) => {
                const isChosen = chosen === oi;
                const isAnswer = graded && graded.answer_index === oi;
                return (
                  <label
                    key={oi}
                    className={cxOption(
                      isChosen && !graded && "border-primary bg-primary/5",
                      graded && isAnswer && "border-success bg-success/10",
                      graded && isChosen && !graded.correct &&
                        "border-danger bg-danger/10",
                    )}
                  >
                    <input
                      type="radio"
                      name={q.id}
                      checked={isChosen}
                      disabled={Boolean(result)}
                      onChange={() =>
                        setAnswers((a) => ({ ...a, [q.id]: oi }))
                      }
                      className="mr-2"
                    />
                    <span className="text-sm">{opt}</span>
                    {graded && isAnswer && (
                      <span className="ml-2 text-xs text-success">correct answer</span>
                    )}
                  </label>
                );
              })}
            </div>
            {graded && (
              <p className={cxExplanation(graded.correct)}>
                {graded.correct ? "Correct. " : "Not quite. "}
                {graded.explanation}
              </p>
            )}
          </div>
        );
      })}

      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="flex gap-2">
        {!result ? (
          <Button
            onClick={submit}
            disabled={!answered || submitting}
            size="sm"
          >
            {submitting ? "Grading..." : "Submit quiz"}
          </Button>
        ) : (
          <Button onClick={retry} size="sm" variant="outline">
            Retake quiz
          </Button>
        )}
        {result && (
          <span className="self-center text-sm font-semibold">
            Score: {result.score}/{result.total}
          </span>
        )}
      </div>
    </div>
  );
}

function cxOption(...parts: (string | boolean | undefined)[]) {
  return [
    "flex cursor-pointer items-start rounded-lg border border-border px-3 py-2",
    "hover:border-muted/60 has-[:disabled]:cursor-default has-[:disabled]:hover:border-border",
    ...parts.filter(Boolean),
  ].join(" ");
}

function cxExplanation(correct: boolean) {
  // (static class names so Tailwind keeps them in the build)
  return correct
    ? "mt-2 text-xs leading-5 text-success"
    : "mt-2 text-xs leading-5 text-warning";
}
