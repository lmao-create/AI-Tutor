export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function timeAgo(iso: string): string {
  const then = new Date(iso.replace(" ", "T") + "Z").getTime();
  if (Number.isNaN(then)) return iso;
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString();
}

export const ACTIVITY_LABELS: Record<string, string> = {
  lesson_completed: "Completed a lesson",
  quiz_taken: "Took a quiz",
  exercise_submitted: "Submitted an exercise",
  hint_revealed: "Used a hint",
  solution_viewed: "Viewed a solution",
  playground_run: "Ran code in the playground",
  chat_started: "Started a chat",
  chat_message: "Asked the tutor a question",
  chat_error: "AI request failed",
  explain_used: "Used the code explainer",
  debug_used: "Used the debugging assistant",
  milestone_completed: "Completed a project milestone",
};

export function activityLabel(kind: string): string {
  return ACTIVITY_LABELS[kind] ?? kind.replace(/_/g, " ");
}
