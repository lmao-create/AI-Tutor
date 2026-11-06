import { Link } from "react-router-dom";

/** Shown when no AI provider is configured - clearly labels demo mode. */
export function DemoBanner() {
  return (
    <div className="border-b border-warning/30 bg-warning/10 px-4 py-2 text-center text-xs text-warning">
      <strong className="font-semibold">Demo mode:</strong> no AI provider is
      configured, so the AI tutor and code review are unavailable. All lessons,
      exercises, quizzes, the playground and progress tracking work offline.{" "}
      <Link to="/settings" className="underline hover:no-underline">
        Add a provider in Settings
      </Link>
      .
    </div>
  );
}
