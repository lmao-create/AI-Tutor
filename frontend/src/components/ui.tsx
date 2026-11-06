import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { cx } from "../lib/utils";

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */
type ButtonVariant = "primary" | "ghost" | "danger" | "success" | "outline";
type ButtonSize = "sm" | "md";

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  const variants: Record<ButtonVariant, string> = {
    primary: "bg-primary text-white hover:bg-primaryHover",
    ghost: "bg-transparent text-fg hover:bg-surfaceHover",
    danger: "bg-danger/90 text-white hover:bg-danger",
    success: "bg-success/90 text-black hover:bg-success",
    outline: "border border-border bg-transparent text-fg hover:bg-surfaceHover",
  };
  const sizes: Record<ButtonSize, string> = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
  };
  return (
    <button
      className={cx("btn-base", variants[variant], sizes[size], className)}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */
export function Card({
  className,
  children,
  as,
}: {
  className?: string;
  children?: ReactNode;
  as?: "section" | "article" | "div";
}) {
  const Tag = as ?? "section";
  return (
    <Tag className={cx("card p-5", className)}>
      {children}
    </Tag>
  );
}

/* ------------------------------------------------------------------ */
/* Badge                                                              */
/* ------------------------------------------------------------------ */
export function Badge({
  tone = "default",
  children,
  className,
}: {
  tone?: "default" | "success" | "warning" | "danger" | "primary" | "muted";
  children: ReactNode;
  className?: string;
}) {
  const tones: Record<string, string> = {
    default: "border-border text-muted",
    success: "border-success/40 text-success",
    warning: "border-warning/40 text-warning",
    danger: "border-danger/40 text-danger",
    primary: "border-primary/50 text-primary",
    muted: "border-muted/30 text-muted",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* ProgressBar                                                         */
/* ------------------------------------------------------------------ */
export function ProgressBar({
  value,
  className,
  tone = "primary",
}: {
  value: number;
  className?: string;
  tone?: "primary" | "success" | "accent";
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const tones = {
    primary: "bg-primary",
    success: "bg-success",
    accent: "bg-accent",
  };
  return (
    <div
      className={cx(
        "h-2 w-full overflow-hidden rounded-full bg-border/60",
        className,
      )}
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cx("h-full rounded-full transition-all", tones[tone])}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Spinner / Skeleton / Empty / Error states                           */
/* ------------------------------------------------------------------ */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cx(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent",
        className,
      )}
      aria-label="Loading"
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cx("animate-pulse rounded-md bg-border/50", className)} />
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border p-10 text-center">
      {icon && <div className="mb-3 text-muted">{icon}</div>}
      <h3 className="text-base font-semibold">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-sm text-muted">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: { message: string; code?: string } | null;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-xl border border-danger/40 bg-danger/5 p-6">
      <h3 className="text-sm font-semibold text-danger">
        Something went wrong
      </h3>
      <p className="mt-1 text-sm text-muted">
        {error?.message ?? "Unknown error."}
        {error?.code ? ` (code: ${error.code})` : ""}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Modal                                                               */
/* ------------------------------------------------------------------ */
export function Modal({
  open,
  title,
  children,
  onClose,
  footer,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative z-10 w-full max-w-lg rounded-xl border border-border bg-surface p-5 shadow-xl animate-slide-in"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">{title}</h2>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            &times;
          </Button>
        </div>
        <div className="text-sm text-muted">{children}</div>
        {footer && <div className="mt-5 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Form controls                                                       */
/* ------------------------------------------------------------------ */
export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium">
      {children}
    </label>
  );
}

export function Input({
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx("input-base", className)} {...rest} />;
}

export function Textarea({
  className,
  ...rest
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cx("input-base min-h-24 font-mono text-xs", className)}
      {...rest}
    />
  );
}

export function Select({
  className,
  children,
  ...rest
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx("input-base", className)} {...rest}>
      {children}
    </select>
  );
}

/* ------------------------------------------------------------------ */
/* Tabs                                                                */
/* ------------------------------------------------------------------ */
export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-surface p-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors",
            active === t.id
              ? "bg-primary/15 text-primary"
              : "text-muted hover:text-fg",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Toasts                                                              */
/* ------------------------------------------------------------------ */
interface Toast {
  id: number;
  message: string;
  tone: "success" | "danger" | "info";
}

const ToastContext = createContext<{
  toast: (message: string, tone?: Toast["tone"]) => void;
}>({ toast: () => {} });

let toastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback(
    (message: string, tone: Toast["tone"] = "success") => {
      const id = ++toastId;
      setToasts((t) => [...t, { id, message, tone }]);
      setTimeout(
        () => setToasts((t) => t.filter((x) => x.id !== id)),
        4200,
      );
    },
    [],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto rounded-lg border px-4 py-2 text-sm shadow-lg animate-slide-in",
              t.tone === "success" && "border-success/40 bg-success/10 text-success",
              t.tone === "danger" && "border-danger/40 bg-danger/10 text-danger",
              t.tone === "info" && "border-border bg-surface text-fg",
            )}
            role="status"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
