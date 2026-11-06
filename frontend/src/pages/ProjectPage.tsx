import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { Project } from "../api/types";
import { CodeEditor } from "../components/CodeEditor";
import { Markdown } from "../components/Markdown";
import {
  Badge,
  Button,
  Card,
  Skeleton,
  useToast,
} from "../components/ui";
import { cx } from "../lib/utils";

export default function ProjectPage() {
  const { slug = "" } = useParams();
  const { data: project, error, loading, refresh } =
    useApi<Project>(`/projects/${slug}`);
  const { toast } = useToast();
  const [openMilestone, setOpenMilestone] = useState<number | null>(0);

  if (loading) return <Skeleton className="h-96" />;
  if (error || !project) {
    return (
      <p className="text-sm text-danger">
        {error?.message ?? "Project not found."}
      </p>
    );
  }

  const proj = project;
  const completed = new Set(proj.completed_milestones ?? []);
  const milestones = proj.milestones ?? [];
  const requirements = proj.requirements ?? [];
  const challenges = proj.challenges ?? [];
  const nextIndex = milestones.findIndex((_, i) => !completed.has(i));

  async function toggleMilestone(index: number) {
    if (completed.has(index)) {
      await api.del(`/projects/${proj.slug}/milestones/${index}/complete`);
      toast("Milestone un-checked.", "info");
    } else {
      await api.post(
        `/projects/${proj.slug}/milestones/${index}/complete`,
        {},
      );
      toast("Milestone complete - nice progress!", "success");
    }
    refresh();
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/projects"
            className="text-sm text-primary hover:underline"
          >
            ← All projects
          </Link>
          <Badge>level {proj.difficulty}</Badge>
          <Badge tone="muted">{proj.language}</Badge>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {proj.title}
        </h1>
        <p className="text-sm text-muted">{proj.description}</p>
        <div className="flex flex-wrap gap-1">
          {proj.skills.map((s) => (
            <span
              key={s}
              className="rounded border border-border px-2 py-0.5 text-xs text-muted"
            >
              {s}
            </span>
          ))}
        </div>
      </header>

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Requirements</h2>
        <ul className="list-disc pl-5 text-sm text-muted">
          {requirements.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </Card>

      <section>
        <h2 className="mb-3 text-base font-semibold">
          Build it step by step ({completed.size}/{milestones.length})
        </h2>
        <div className="space-y-3">
          {milestones.map((m, i) => {
            const locked = nextIndex >= 0 && i > nextIndex;
            const open = openMilestone === i;
            return (
              <Card
                key={m.title}
                className={cx(
                  locked && "opacity-70",
                  completed.has(i) && "border-success/40",
                )}
              >
                <div className="flex items-start gap-3">
                  <button
                    onClick={() => toggleMilestone(i)}
                    aria-label={
                      completed.has(i)
                        ? `Undo milestone ${m.title}`
                        : `Complete milestone ${m.title}`
                    }
                    className={cx(
                      "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded border text-xs",
                      completed.has(i)
                        ? "border-success/60 bg-success/20 text-success"
                        : "border-border text-transparent hover:border-muted",
                    )}
                  >
                    ✓
                  </button>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium">
                        {i + 1}. {m.title}
                      </p>
                      {locked && <Badge tone="muted">later</Badge>}
                      {completed.has(i) && (
                        <Badge tone="success">done</Badge>
                      )}
                    </div>
                    <p className="mt-0.5 text-sm text-muted">{m.goal}</p>

                    {!locked && (
                      <div className="mt-2 flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setOpenMilestone(open ? null : i)}
                        >
                          {open ? "Hide guidance" : "Show guidance"}
                        </Button>
                        <Link
                          to={`/tutor?project=${encodeURIComponent(
                            proj.title,
                          )}&stage=${encodeURIComponent(m.title)}`}
                        >
                          <Button variant="ghost" size="sm">
                            Ask the tutor about this stage
                          </Button>
                        </Link>
                      </div>
                    )}

                    {open && !locked && (
                      <div className="mt-3 border-t border-border pt-3">
                        <Markdown content={m.guidance} />
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {proj.starter_code && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Starter code</h2>
          <CodeEditor
            value={proj.starter_code}
            readOnly
            height="220px"
            fontSize={13}
          />
          <div className="mt-2 flex gap-2">
            <Link to="/playground" state={{ code: proj.starter_code }}>
              <Button size="sm" variant="outline">
                Open in Playground
              </Button>
            </Link>
          </div>
        </Card>
      )}

      <Card>
        <h2 className="mb-2 text-sm font-semibold">How to test it</h2>
        <Markdown content={proj.testing_instructions ?? ""} />
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Optional challenges</h2>
        <ul className="list-disc pl-5 text-sm text-muted">
          {challenges.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Card>

      {completed.size === milestones.length && milestones.length > 0 && (
        <Card className="border-success/40 bg-success/5">
          <h2 className="text-sm font-semibold text-success">
            Project complete!
          </h2>
          <p className="mt-1 text-sm text-muted">
            Every milestone is checked off. Do a final self-review: does the
            program handle odd input? Can a stranger run it with zero
            guidance? Then modify it - add a feature of your own - and share
            it.
          </p>
        </Card>
      )}
    </div>
  );
}
