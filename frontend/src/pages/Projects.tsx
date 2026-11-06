import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import type { Project } from "../api/types";
import {
  Badge,
  Card,
  ProgressBar,
  Skeleton,
} from "../components/ui";

export default function Projects() {
  const { data, error, loading } = useApi<{ projects: Project[] }>("/projects");

  if (loading) return <Skeleton className="h-64" />;
  if (error) {
    return <p className="text-sm text-danger">{error.message}</p>;
  }

  const projects = data?.projects ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Guided projects
        </h1>
        <p className="mt-1 text-sm text-muted">
          Build real programs in small, verifiable stages. Each project gives
          you requirements, milestones, a testing checklist and stretch goals -
          and never dumps the finished code on you all at once.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        {projects.map((p) => {
          const total = p.milestones_total ?? 0;
          const percent = total > 0 ? (p.milestones_completed! / total) * 100 : 0;
          return (
            <Link key={p.slug} to={`/projects/${p.slug}`}>
              <Card className="h-full transition-colors hover:border-primary/50">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium">{p.title}</p>
                  <Badge>level {p.difficulty}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted">{p.description}</p>
                <div className="mt-3">
                  <ProgressBar value={percent} />
                  <p className="mt-1 text-xs text-muted">
                    {p.milestones_completed} of {total} milestones
                  </p>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {p.skills.slice(0, 4).map((s) => (
                    <span
                      key={s}
                      className="rounded border border-border px-1.5 py-0.5 text-xs text-muted"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
