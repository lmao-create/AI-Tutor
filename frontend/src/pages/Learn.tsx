import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import type { Course } from "../api/types";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  ProgressBar,
  Skeleton,
} from "../components/ui";
import { Markdown } from "../components/Markdown";

export default function Learn() {
  const { data, error, loading } = useApi<{ courses: Course[] }>("/courses");

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-40" />
        ))}
      </div>
    );
  }
  if (error || !data) {
    return <ErrorState error={error} />;
  }

  const { courses } = data;
  const complete = courses.filter((c) => c.status === "complete");
  const planned = courses.filter((c) => c.status === "planned");

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Learning paths</h1>
        <p className="mt-1 text-sm text-muted">
          Structured courses ordered by difficulty. The Python path is fully
          built out today; other paths are marked as in development - their
          pages never claim finished lessons that do not exist.
        </p>
      </header>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
          Available now ({complete.length})
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {complete.map((c) => (
            <Link key={c.slug} to={`/learn/${c.slug}`}>
              <Card className="h-full transition-colors hover:border-primary/50">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{c.title}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {c.language} · {c.level} · {c.lessons_total} lessons
                    </p>
                  </div>
                  <Badge tone="success">Complete</Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-muted">
                  {c.description}
                </p>
                <div className="mt-3">
                  <ProgressBar value={c.percent} />
                  <p className="mt-1 text-xs text-muted">
                    {c.percent}% completed ({c.lessons_completed}/{c.lessons_total})
                  </p>
                </div>
              </Card>
            </Link>
          ))}
        </div>
        {complete.length === 0 && (
          <EmptyState title="No complete course yet." />
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
          In development ({planned.length})
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {planned.map((c) => (
            <Card key={c.slug} className="h-full opacity-80">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{c.title}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {c.language} · {c.level}
                  </p>
                </div>
                <Badge tone="warning">Coming soon</Badge>
              </div>
              <p className="mt-2 text-sm text-muted">{c.description}</p>
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-primary">
                  Planned topics
                </summary>
                <ul className="mt-1 list-disc pl-5 text-xs text-muted">
                  {c.outline.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </details>
              <p className="mt-2 text-xs text-muted">
                No lessons are available yet. This page shows the planned scope
                so nothing is overpromised. Start with the Python path - the
                skills transfer.
              </p>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
