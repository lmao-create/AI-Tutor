import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { ProgressData } from "../api/types";
import {
  Button,
  Card,
  EmptyState,
  Modal,
  ProgressBar,
  Skeleton,
  useToast,
} from "../components/ui";
import { cx, formatDuration, timeAgo, activityLabel } from "../lib/utils";

export default function ProgressPage() {
  const { data: p, error, loading, refresh } =
    useApi<ProgressData>("/progress");
  const { toast } = useToast();
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);

  async function reset() {
    setResetting(true);
    try {
      await api.post("/progress/reset", { confirm: true });
      toast("Progress reset. A clean start!", "info");
      setResetOpen(false);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Reset failed.", "danger");
    } finally {
      setResetting(false);
    }
  }

  if (loading) return <Skeleton className="h-96" />;
  if (error || !p) {
    return <p className="text-sm text-danger">{error?.message}</p>;
  }

  const o = p.overall;
  const weak = p.topics.weaknesses;
  const strong = p.topics.strengths;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Your progress
          </h1>
          <p className="mt-1 text-sm text-muted">
            Every number here comes from your actual lesson completions, quiz
            results and exercise attempts.
          </p>
        </div>
        <Button variant="danger" size="sm" onClick={() => setResetOpen(true)}>
          Reset progress...
        </Button>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs text-muted">Overall</p>
          <p className="mt-1 text-2xl font-semibold">{o.percent}%</p>
          <ProgressBar className="mt-2" value={o.percent} />
          <p className="mt-1 text-xs text-muted">
            {o.lessons_completed} of {o.lessons_total} lessons
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted">Streak</p>
          <p className="mt-1 text-2xl font-semibold">
            {p.streak.current}{" "}
            <span className="text-sm font-normal text-muted">
              day{p.streak.current === 1 ? "" : "s"}
            </span>
          </p>
          <p className="mt-1 text-xs text-muted">best ever: {p.streak.best}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted">Quiz average</p>
          <p className="mt-1 text-2xl font-semibold">
            {Math.round(o.quiz_average)}%
          </p>
          <p className="mt-1 text-xs text-muted">
            {o.quizzes_taken} quiz{o.quizzes_taken === 1 ? "" : "zes"} taken
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted">Exercises passed</p>
          <p className="mt-1 text-2xl font-semibold">{o.exercises_passed}</p>
          <p className="mt-1 text-xs text-muted">
            {o.projects_completed} project{o.projects_completed === 1 ? "" : "s"} completed
          </p>
        </Card>
      </div>

      {p.recommended_lesson && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">Recommended next</h2>
              <p className="mt-1 font-medium">
                {p.recommended_lesson.title}
              </p>
              <p className="text-xs text-muted">
                {p.recommended_lesson.course_title}
              </p>
            </div>
            <Link
              to={`/learn/${p.recommended_lesson.course_slug}/${p.recommended_lesson.slug}`}
            >
              <Button size="sm">Continue</Button>
            </Link>
          </div>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Strengths</h2>
          {strong.length === 0 ? (
            <p className="text-sm text-muted">
              Pass some quizzes and exercises to see your strengths here.
            </p>
          ) : (
            <ul className="space-y-2">
              {strong.map((t) => (
                <li key={t.lesson_id} className="text-sm">
                  <div className="flex justify-between">
                    <Link
                      to={`/learn/python/${t.slug}`}
                      className="hover:text-primary"
                    >
                      {t.title}
                    </Link>
                    <span className="text-xs text-success">
                      {t.score}%
                    </span>
                  </div>
                  <ProgressBar
                    value={t.score}
                    className="mt-1"
                    tone="success"
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Needs review</h2>
          {weak.length === 0 ? (
            <p className="text-sm text-muted">
              Nothing flagged right now - whatever you have attempted is solid.
            </p>
          ) : (
            <ul className="space-y-2">
              {weak.map((t) => (
                <li key={t.lesson_id} className="text-sm">
                  <div className="flex justify-between">
                    <Link
                      to={`/learn/python/${t.slug}`}
                      className="hover:text-primary"
                    >
                      {t.title}
                    </Link>
                    <span className="text-xs text-warning">{t.score}%</span>
                  </div>
                  <ProgressBar
                    value={t.score}
                    className="mt-1"
                    tone="accent"
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <section>
        <h2 className="mb-3 text-base font-semibold">Achievements</h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {p.achievements.map((a) => (
            <Card
              key={a.id}
              className={cx(
                "p-3",
                a.earned && "border-primary/40 bg-primary/5",
              )}
            >
              <div className="flex items-center gap-2">
                <span className={a.earned ? "text-primary" : "text-muted"}>
                  {a.earned ? "🏆" : "🔒"}
                </span>
                <p className="text-sm font-medium">{a.label}</p>
              </div>
              <p className="mt-0.5 text-xs text-muted">{a.description}</p>
              {!a.earned && a.progress > 0 && (
                <ProgressBar className="mt-2" value={a.progress * 100} />
              )}
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold">Activity feed</h2>
        {p.recent_activity.length === 0 ? (
          <EmptyState
            title="Nothing yet"
            description="Complete a lesson or run code in the playground to start your history."
          />
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
            {p.recent_activity.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between px-4 py-2 text-sm"
              >
                <span>{activityLabel(a.kind)}</span>
                <span className="text-xs text-muted">
                  {timeAgo(a.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-xs text-muted">
        Tracked learning time:{" "}
        <strong className="text-fg">
          {formatDuration(o.tracked_time_seconds)}
        </strong>{" "}
        (lesson time is measured between opening and completing a lesson - an
        honest approximation, not a stopwatch on your attention).
      </p>

      <Modal
        open={resetOpen}
        title="Reset all learning progress?"
        onClose={() => setResetOpen(false)}
        footer={
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setResetOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={reset}
              disabled={resetting}
            >
              {resetting ? "Resetting..." : "Yes, reset everything"}
            </Button>
          </>
        }
      >
        <p>
          This erases every completed lesson, quiz result, exercise attempt,
          project milestone and streak. Your chats and provider settings stay.
          This cannot be undone - are you sure?
        </p>
      </Modal>
    </div>
  );
}
