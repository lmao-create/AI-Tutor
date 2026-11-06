import { useEffect, useRef, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { Lesson } from "../api/types";
import { Markdown } from "../components/Markdown";
import { CodeEditor } from "../components/CodeEditor";
import { Quiz } from "../components/Quiz";
import { ExercisePanel } from "../components/ExercisePanel";
import {
  Button,
  Card,
  ErrorState,
  Skeleton,
  useToast,
} from "../components/ui";
import { formatDuration } from "../lib/utils";

export default function LessonPage() {
  const { courseSlug = "", lessonSlug = "" } = useParams();
  const navigate = useNavigate();
  const { data: lesson, error, loading, refresh } =
    useApi<Lesson>(`/courses/${courseSlug}/lessons/${lessonSlug}`);
  const { toast } = useToast();
  const [saved, setSaved] = useState(false);
  const [completing, setCompleting] = useState(false);
  const openedAt = useRef(Date.now());

  // Track how long the learner stays on the lesson (server-side learning time).
  useEffect(() => {
    openedAt.current = Date.now();
    return () => undefined;
  }, [lessonSlug]);

  async function completeLesson() {
    if (!lesson) return;
    setCompleting(true);
    try {
      const seconds = Math.max(
        1,
        Math.round((Date.now() - openedAt.current) / 1000),
      );
      await api.post(`/lessons/${lesson.id}/complete`, {
        time_spent_seconds: seconds,
      });
      setSaved(true);
      refresh();
      toast(`Nice work - you spent ${formatDuration(seconds)} on this lesson.`,
        "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not mark complete.",
        "danger");
    } finally {
      setCompleting(false);
    }
  }

  function goNext() {
    if (lesson?.next_lesson) {
      navigate(`/learn/${lesson.course_slug}/${lesson.next_lesson}`);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
    );
  }
  if (error || !lesson) {
    return <ErrorState error={error} />;
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <Link to="/learn" className="hover:text-fg">
            Learning paths
          </Link>
          <span>/</span>
          <Link to={`/learn/${lesson.course_slug}`} className="hover:text-fg">
            {lesson.course_title}
          </Link>
          <span>/</span>
          <span>Lesson</span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {lesson.title}
          </h1>
          {(lesson.completed || saved) && (
            <span className="rounded-full border border-success/40 px-2.5 py-0.5 text-xs text-success">
              ✓ Completed
            </span>
          )}
        </div>
        <p className="text-sm text-muted">{lesson.summary}</p>
      </header>

      <Card>
        <h2 className="mb-2 text-sm font-semibold">What you will learn</h2>
        <ul className="list-disc pl-5 text-sm text-muted">
          {lesson.objectives.map((o) => (
            <li key={o}>{o}</li>
          ))}
        </ul>
      </Card>

      {lesson.sections.map((s, i) => (
        <section key={i} className="space-y-2">
          <h2 className="text-lg font-semibold">{s.heading}</h2>
          <Markdown content={s.body} />
          {s.code && (
            <div className="not-prose">
              <ExampleCode code={s.code} />
            </div>
          )}
        </section>
      ))}

      {lesson.example?.code && (
        <Card className="space-y-3">
          <h2 className="text-sm font-semibold">
            Worked example: {lesson.example.title}
          </h2>
          <ExampleCode code={lesson.example.code} />
          <Markdown content={lesson.example.explanation} />
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              const code = lesson.example.code;
              navigate("/playground", { state: { code } });
            }}
          >
            Open this example in the Playground
          </Button>
        </Card>
      )}

      {lesson.quiz.length > 0 && (
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold">Quick quiz</h2>
          <Quiz
            lessonId={lesson.id}
            questions={lesson.quiz}
            bestScore={lesson.quiz_best}
            onSubmitted={refresh}
          />
        </Card>
      )}

      {lesson.exercise && (
        <Card className="space-y-4">
          <h2 className="text-sm font-semibold">Practice exercise</h2>
          <ExercisePanel
            exercise={lesson.exercise}
            onStatusChange={refresh}
          />
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          disabled={!lesson.prev_lesson}
          onClick={() => {
            if (lesson.prev_lesson) {
              navigate(`/learn/${lesson.course_slug}/${lesson.prev_lesson}`);
            }
          }}
        >
          ← Previous
        </Button>
        <Button
          size="sm"
          onClick={completeLesson}
          disabled={completing || lesson.completed}
          variant={lesson.completed ? "success" : "primary"}
        >
          {completing
            ? "Saving..."
            : lesson.completed
              ? "Completed"
              : "Mark lesson complete"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={!lesson.next_lesson}
          onClick={goNext}
        >
          Next →
        </Button>
        {lesson.time_spent_seconds > 0 && (
          <span className="text-xs text-muted">
            Tracked time: {formatDuration(lesson.time_spent_seconds)}
          </span>
        )}
      </div>
    </div>
  );
}

function ExampleCode({ code }: { code: string }) {
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setOutput(null);
    try {
      const res = await api.post<{
        stdout: string;
        stderr: string;
        exit_code: number;
        error_info: { message: string; line?: number; type: string } | null;
      }>("/execution/run", { language: "python", code });
      if (res.error_info) {
        setOutput(
          [res.stdout, res.stderr, res.error_info.type + ": "
            + res.error_info.message].filter(Boolean).join("\n"),
        );
      } else {
        setOutput([res.stdout, res.stderr].filter(Boolean).join(""));
      }
    } catch (e) {
      setOutput("Could not run the example: " + (e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-2">
      <CodeEditor value={code} readOnly height="auto" fontSize={13} />
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={run} disabled={running}>
          {running ? "Running..." : "▶ Run this example"}
        </Button>
        {output !== null && (
          <Button variant="ghost" size="sm" onClick={() => setOutput(null)}>
            Clear output
          </Button>
        )}
      </div>
      {output !== null && (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-border bg-bg p-3 text-xs">
          {output || "(no output - try printing a value)"}
        </pre>
      )}
    </div>
  );
}
