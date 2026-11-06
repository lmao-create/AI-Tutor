import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import type {
  Course,
  ProgressData,
  HealthInfo,
} from "../api/types";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  ProgressBar,
  Skeleton,
} from "../components/ui";
import { formatDuration, timeAgo, activityLabel } from "../lib/utils";

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </Card>
  );
}

export default function Dashboard() {
  const { data: progress, error, loading } = useApi<ProgressData>("/progress");
  const { data: courses } = useApi<{ courses: Course[] }>("/courses");
  const { data: health } = useApi<HealthInfo>("/health");

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-40" />
      </div>
    );
  }
  if (error || !progress) {
    return <ErrorState error={error} />;
  }

  const o = progress.overall;
  const rec = progress.recommended_lesson;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section>
        <h1 className="text-2xl font-semibold tracking-tight">
          {progress.streak.current > 0
            ? "Welcome back - let's keep the streak alive."
            : "Welcome to CodeTutor AI."}
        </h1>
        <p className="mt-1 text-sm text-muted">
          A patient AI programming teacher: short lessons, real exercises,
          real feedback on your code - step by step, at your own level.
        </p>
      </section>

      {/* Stats */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Lessons completed"
          value={`${o.lessons_completed}/${o.lessons_total}`}
          sub={`${o.percent}% of the Python path`}
        />
        <StatCard
          label="Current streak"
          value={`${progress.streak.current} day${progress.streak.current === 1 ? "" : "s"}`}
          sub={`Best: ${progress.streak.best}`}
        />
        <StatCard
          label="Exercises passed"
          value={o.exercises_passed}
          sub={`Quiz average: ${o.quiz_average}%`}
        />
        <StatCard
          label="Tracked learning time"
          value={formatDuration(o.tracked_time_seconds)}
          sub={`${o.projects_completed} project${o.projects_completed === 1 ? "" : "s"} finished`}
        />
      </div>

      {/* Continue learning */}
      <Card className="space-y-3">
        {rec ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold">Continue learning</h2>
              <Badge tone="primary">Recommended next</Badge>
            </div>
            <div>
              <p className="text-xs text-muted">{rec.course_title}</p>
              <p className="text-lg font-medium">{rec.title}</p>
              <p className="mt-1 text-sm text-muted">{rec.summary}</p>
            </div>
            <Link
              to={`/learn/${rec.course_slug}/${rec.slug}`}
              className="inline-block"
            >
              <Button size="sm">Start the lesson</Button>
            </Link>
          </>
        ) : (
          <EmptyState
            title="Every Python lesson is complete!"
            description="You finished the whole course. Pick a guided project or explore the AI tools to practice."
          />
        )}
      </Card>

      {/* Courses */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Learning paths</h2>
          <Link to="/learn" className="text-sm text-primary hover:underline">
            See all
          </Link>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {(courses?.courses ?? [])
            .filter((c) => c.status === "complete" || c.slug === "python")
            .slice(0, 4)
            .map((c) => (
              <Link key={c.slug} to={`/learn/${c.slug}`}>
                <Card className="h-full transition-colors hover:border-primary/50">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{c.title}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {c.language} · {c.level}
                      </p>
                    </div>
                    <Badge
                      tone={c.status === "complete" ? "success" : "warning"}
                    >
                      {c.status === "complete" ? "Complete" : "In development"}
                    </Badge>
                  </div>
                  <div className="mt-3">
                    <ProgressBar value={c.percent} />
                    <p className="mt-1 text-xs text-muted">
                      {c.lessons_completed} of {c.lessons_total} lessons
                    </p>
                  </div>
                </Card>
              </Link>
            ))}
        </div>
      </section>

      {/* Recent activity */}
      <section>
        <h2 className="mb-3 text-base font-semibold">Recent activity</h2>
        {progress.recent_activity.length === 0 ? (
          <EmptyState
            title="No activity yet"
            description="Complete your first lesson and it will show up here."
          />
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
            {progress.recent_activity.slice(0, 8).map((a) => (
              <li key={a.id} className="flex items-center justify-between px-4 py-2 text-sm">
                <span>{activityLabel(a.kind)}</span>
                <span className="text-xs text-muted">
                  {timeAgo(a.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Provider status hint */}
      {health && health.demo_mode && (
        <p className="text-xs text-muted">
          Running in demo mode: lessons, exercises and the playground work
          offline. Add an API provider to unlock the AI tutor, code review and
          the explainer.{" "}
          <Link to="/settings" className="text-primary hover:underline">
            Open Settings
          </Link>
          .
        </p>
      )}
    </div>
  );
}
