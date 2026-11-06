/** Shared API types (mirrors the backend schemas). */

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(message: string, status: number, code = `http_${status}`) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export interface ProviderView {
  configured: boolean;
  source: "settings" | "env" | null;
  provider_name: string | null;
  base_url: string | null;
  model: string | null;
  key_masked: string | null;
}

export interface ProviderTestResult {
  ok: boolean;
  code: string;
  message: string;
  latency_ms?: number;
  models?: string[];
  model_known?: boolean;
  model_hint?: string;
}

export interface TestResult {
  case?: number;
  call?: string;
  ok: boolean;
  got?: string;
  expected?: string;
  error?: string;
}

export interface QuizQuestionOut {
  id: string;
  correct: boolean;
  chosen: number | null;
  answer_index: number;
  explanation: string;
}

export interface QuizResult {
  score: number;
  total: number;
  best: number | null;
  per_question: QuizQuestionOut[];
}

export interface TutorMode {
  id: string;
  label: string;
  description: string;
}

export interface Conversation {
  id: number;
  title: string;
  mode: string;
  created_at: string;
  updated_at: string;
  preview: string | null;
  message_count: number;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  mode: string | null;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Course {
  id: number;
  slug: string;
  title: string;
  description: string;
  language: string;
  level: string;
  status: "complete" | "planned";
  overview: string;
  prerequisites: string[];
  outline: string[];
  lessons_total: number;
  lessons_completed: number;
  percent: number;
}

export interface LessonSection {
  heading: string;
  body: string;
  code?: string;
}

export interface LessonListItem {
  id: number;
  slug: string;
  title: string;
  summary: string;
  order_index: number;
  completed: boolean;
  quiz_best: number | null;
}

export interface LessonExample {
  title: string;
  code: string;
  explanation: string;
}

export interface Lesson {
  id: number;
  slug: string;
  title: string;
  summary: string;
  objectives: string[];
  sections: LessonSection[];
  example: LessonExample;
  quiz: { id: string; question: string; options: string[] }[];
  course_slug: string;
  course_title: string;
  completed: boolean;
  time_spent_seconds: number;
  quiz_best: number | null;
  prev_lesson: string | null;
  next_lesson: string | null;
  exercise: Exercise | null;
}

export interface CourseDetail extends Course {
  lessons: LessonListItem[];
}

export interface Exercise {
  id: number;
  slug: string;
  course_id: number | null;
  lesson_id: number | null;
  kind: string;
  title: string;
  prompt: string;
  difficulty: number;
  language: string;
  starter_code: string;
  order_index: number;
  hint_count: number;
  options?: string[] | null;
  status?: ExerciseStatus;
}

export interface ExerciseStatus {
  attempts: number;
  passed: boolean;
  hints_revealed: number;
}

export interface SubmitResult {
  passed: boolean;
  kind: string;
  feedback: {
    message: string;
    tests?: TestResult[];
    answer_index?: number;
    answer_line?: number;
    your_answer?: string;
  };
  run?: ExecResult;
  explanation: string | null;
  status: ExerciseStatus;
}

export interface HintResponse {
  type: "hint" | "solution";
  level: number;
  total_hints: number;
  content?: string;
  solution_available_after?: number;
  code?: string;
  explanation?: string;
}

export interface ExecResult {
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  duration_ms: number;
  error_info: { type: string; message: string; line?: number } | null;
  truncated: boolean;
}

export interface LanguageInfo {
  id: string;
  label: string;
  executable: boolean;
  version: string;
  timeout_seconds: number;
  notes: string;
}

export interface ExplainMode {
  id: string;
  label: string;
  description: string;
}

export interface Achievement {
  id: string;
  label: string;
  description: string;
  earned: boolean;
  progress: number;
}

export interface ProgressData {
  overall: {
    lessons_total: number;
    lessons_completed: number;
    percent: number;
    quizzes_taken: number;
    quiz_average: number;
    exercises_passed: number;
    tracked_time_seconds: number;
    projects_completed: number;
  };
  per_course: {
    slug: string;
    title: string;
    status: string;
    lessons_total: number;
    lessons_completed: number;
    percent: number;
  }[];
  streak: { current: number; best: number; active_today: boolean };
  recommended_lesson: {
    lesson_id: number;
    slug: string;
    title: string;
    summary: string;
    course_slug: string;
    course_title: string;
  } | null;
  topics: {
    strengths: { lesson_id: number; title: string; slug: string; score: number }[];
    weaknesses: { lesson_id: number; title: string; slug: string; score: number }[];
  };
  achievements: Achievement[];
  recent_activity: {
    id: number;
    kind: string;
    ref: string;
    detail: Record<string, unknown>;
    created_at: string;
  }[];
}

export interface ProjectMilestone {
  title: string;
  goal: string;
  guidance: string;
}

export interface Project {
  id: number;
  slug: string;
  title: string;
  description: string;
  difficulty: number;
  language: string;
  skills: string[];
  milestones?: ProjectMilestone[];
  requirements?: string[];
  starter_code?: string;
  testing_instructions?: string;
  challenges?: string[];
  milestones_total?: number;
  milestones_completed?: number;
  completed_milestones?: number[];
}

export interface Preferences {
  theme: "dark" | "light";
  active_course: string;
  default_tutor_mode: string;
  editor_font_size: number;
}

export interface HealthInfo {
  status: string;
  app: string;
  version: string;
  db_ok: boolean;
  provider_configured: boolean;
  demo_mode: boolean;
  provider: { name: string; model: string } | null;
}
