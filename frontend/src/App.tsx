import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Learn from "./pages/Learn";
import CoursePage from "./pages/CoursePage";
import LessonPage from "./pages/LessonPage";
import Practice from "./pages/Practice";
import Tutor from "./pages/Tutor";
import Playground from "./pages/Playground";
import Explainer from "./pages/Explainer";
import Debugger from "./pages/Debugger";
import Projects from "./pages/Projects";
import ProjectPage from "./pages/ProjectPage";
import ProgressPage from "./pages/Progress";
import SettingsPage from "./pages/Settings";
import { Button } from "./components/ui";

function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-muted">
        The page you were looking for does not exist.
      </p>
      <Link to="/" className="mt-4 inline-block">
        <Button>Back to dashboard</Button>
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />} path="/">
        <Route index element={<Dashboard />} />
        <Route path="learn" element={<Learn />} />
        <Route path="learn/:courseSlug" element={<CoursePage />} />
        <Route
          path="learn/:courseSlug/:lessonSlug"
          element={<LessonPage />}
        />
        <Route path="practice" element={<Practice />} />
        <Route path="tutor" element={<Tutor />} />
        <Route path="playground" element={<Playground />} />
        <Route path="explainer" element={<Explainer />} />
        <Route path="debugger" element={<Debugger />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:slug" element={<ProjectPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
