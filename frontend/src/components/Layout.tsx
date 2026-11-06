import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useTheme } from "../lib/theme";
import { cx } from "../lib/utils";
import { DemoBanner } from "./DemoBanner";
import { Button, Spinner } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: "M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5" },
  { to: "/learn", label: "Learn", icon: "M4 5.5A1.5 1.5 0 0 1 5.5 4h5A1.5 1.5 0 0 1 12 5.5v13a1.5 1.5 0 0 0-1.5 1.5h-5A1.5 1.5 0 0 1 4 18.5zm8 0A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5v13a1.5 1.5 0 0 0-1.5 1.5h-5A1.5 1.5 0 0 1 10 18.5z" },
  { to: "/practice", label: "Practice", icon: "M5 4h14v6H5zm0 10h14v6H5z" },
  { to: "/tutor", label: "AI Tutor", icon: "M12 3c-4.97 0-9 3.36-9 7.5 0 1.5.49 2.9 1.33 4.1L3 21l3.9-1.33c1.2.84 2.6 1.33 4.1 1.33 4.97 0 9-3.36 9-7.5S16.97 3 12 3z" },
  { to: "/playground", label: "Playground", icon: "M8 6 3 12l5 6M16 6l5 6-5 6" },
  { to: "/explainer", label: "Explainer", icon: "M4 5h16M4 12h9M4 19h13" },
  { to: "/projects", label: "Projects", icon: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" },
  { to: "/progress", label: "Progress", icon: "M4 19V9m5 10V5m5 14v-7" },
  { to: "/settings", label: "Settings", icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm8.4-3a8.4 8.4 0 0 1-.12 1.3l2-1.55-2 3.47v.1c0 .94-.32 1.8-.87 2.48l2 1.55-3.47-2a6 6 0 0 1-2.08.9L12 21l-1.3-2.13a6 6 0 0 1-2.13-.9l-3.47 2 2-1.55A4 4 0 0 1 6.24 16l-3.47 2 2-3.47c-.12-.42-.12-.85-.12-1.3s0-.88.12-1.3l-2-1.55L6.24 8.5A4 4 0 0 1 7.1 6.02l-2-1.55 3.47 2a6 6 0 0 1 2.13-.9L12 3l1.3 2.13c.75.17 1.45.47 2.08.9l3.47-2-2 1.55c.55.68.87 1.54.87 2.48v.1l2 1.48-2 1.55c.12.42.12.85.12 1.3z" },
];

function NavIcon({ d }: { d: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-4 w-4 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={d} />
    </svg>
  );
}

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { data: health, loading } = useApi<{
    demo_mode: boolean;
    provider: { name: string; model: string } | null;
  }>("/health");
  const location = useLocation();

  const closeSidebar = () => setSidebarOpen(false);

  return (
    <div className="flex h-screen flex-col">
      {health?.demo_mode && <DemoBanner />}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside
          className={cx(
            "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-border bg-sidebar transition-transform lg:static lg:translate-x-0",
            sidebarOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex items-center gap-2 border-b border-border px-4 py-3.5">
            <Link to="/" className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-sm font-bold text-white">
                {"</>"}
              </span>
              <span className="text-base font-semibold tracking-tight">
                CodeTutor<span className="text-primary"> AI</span>
              </span>
            </Link>
          </div>
          <nav className="flex-1 space-y-0.5 p-2" aria-label="Main navigation">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={closeSidebar}
                className={({ isActive }) =>
                  cx(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-primary/15 text-primary font-medium"
                      : "text-muted hover:bg-surfaceHover hover:text-fg",
                  )
                }
              >
                <NavIcon d={item.icon} />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="border-t border-border p-3 text-xs text-muted">
            <div className="flex items-center gap-2">
              <span
                className={cx(
                  "h-2 w-2 rounded-full",
                  loading && "bg-muted",
                  !loading && health?.demo_mode && "bg-warning",
                  !loading && health && !health.demo_mode && "bg-success",
                )}
                aria-hidden
              />
              {loading ? (
                "Checking provider..."
              ) : health?.demo_mode ? (
                "Demo mode"
              ) : (
                <span className="truncate" title={health?.provider?.model ?? ""}>
                  {health?.provider?.name ?? "Connected"}
                </span>
              )}
            </div>
          </div>
        </aside>

        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/40 lg:hidden"
            onClick={closeSidebar}
            aria-hidden
          />
        )}

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center gap-3 border-b border-border bg-surface/80 px-4 py-2.5 backdrop-blur lg:px-6">
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </Button>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">
                Learn to program with a patient AI teacher.
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </Button>
          </header>
          <main
            key={location.pathname}
            className="flex-1 overflow-auto p-4 lg:p-6 animate-fade-in"
          >
            <div className="mx-auto max-w-5xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
      {!health && loading && (
        <div className="sr-only">
          <Spinner />
        </div>
      )}
    </div>
  );
}

export { api };
