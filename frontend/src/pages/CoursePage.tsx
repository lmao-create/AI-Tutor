import { Link, useParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import type { CourseDetail } from "../api/types";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  ProgressBar,
  Skeleton,
} from "../components/ui";
import { Markdown } from "../components/Markdown";

export default function CoursePage() {
  const { courseSlug = "" } = useParams();
  const { data, error, loading } = useApi<CourseDetail>(
    `/courses/${courseSlug}`,
  );

  if (loading) return <Skeleton className="h-96" />;
  if (error || !data) return <ErrorState error={error} />;

  return (
    <div className="space-y-6">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" className="px-2">
            <Link to="/learn">← All paths</Link>
          </Button>
          <Badge tone={data.status === "complete" ? "success" : "warning"}>
            {data.status === "complete" ? "Complete course" : "In development"}
          </Badge>
          <Badge>{data.level}</Badge>
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {data.title}
        </h1>
        <p className="mt-1 text-sm text-muted">{data.description}</p>
      </header>

      <Card className="space-y-2">
        <h2 className="text-sm font-semibold">Prerequisites</h2>
        {data.prerequisites.length > 0 ? (
          <ul className="list-disc pl-5 text-sm text-muted">
            {data.prerequisites.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">None - total beginners welcome.</p>
        )}
        <div className="mt-3">
          <ProgressBar value={data.percent} />
          <p className="mt-1 text-xs text-muted">
            {data.lessons_completed} of {data.lessons_total} lessons completed
          </p>
        </div>
      </Card>

      {data.overview && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Course overview</h2>
          <Markdown content={data.overview} />
        </Card>
      )}

      <section>
        <h2 className="mb-3 text-base font-semibold">
          Lessons ({data.lessons.length})
        </h2>
        {data.lessons.length === 0 ? (
          <Card className="border-warning/40 bg-warning/5">
            <p className="text-sm">
              This course is still being written - its lessons are not available
              yet. The Python path above covers the same foundations.
            </p>
          </Card>
        ) : (
          <ol className="overflow-hidden rounded-xl border border-border">
            {data.lessons.map((lesson, i) => (
              <li
                key={lesson.id}
                className="border-b border-border last:border-0"
              >
                <Link
                  to={`/learn/${data.slug}/${lesson.slug}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-surfaceHover"
                >
                  <span
                    className={
                      "grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs " +
                      (lesson.completed
                        ? "border-success/50 bg-success/15 text-success"
                        : "border-border text-muted")
                    }
                    aria-hidden
                  >
                    {lesson.completed ? "✓" : i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {lesson.title}
                    </span>
                    <span className="block truncate text-xs text-muted">
                      {lesson.summary}
                    </span>
                  </span>
                  {lesson.quiz_best != null && (
                    <span className="shrink-0 text-xs text-muted">
                      quiz {lesson.quiz_best}%
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
