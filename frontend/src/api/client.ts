/** API client: typed fetch helpers + a Server-Sent Events stream consumer. */
import { ApiError } from "./types";

const BASE = "/api";

async function request<T>(
  path: string,
  init: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const { body, headers, method, signal } = init;
  const res = await fetch(BASE + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
    signal,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    let code = `http_${res.status}`;
    let message = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error) {
        code = data.error.code ?? code;
        message = data.error.message ?? message;
      }
    } catch {
      /* body wasn't JSON - keep the generic message */
    }
    throw new ApiError(message, res.status, code);
  }
  if (res.status === 204) return null as unknown as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown = {}) =>
    request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body: unknown = {}) =>
    request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body: unknown = {}) =>
    request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) =>
    request<T>(path, { method: "DELETE" }),
};

export interface StreamHandlers {
  onDelta?: (text: string) => void;
  onDone?: (payload: Record<string, unknown>) => void;
  onError?: (code: string, message: string) => void;
  onState?: (state: "start" | "stop") => void;
}

/**
 * POST to a streaming SSE endpoint and dispatch parsed events.
 * Returns whatever `onDone` collected, or rethrows on stream-level errors.
 */
export async function streamSse(
  path: string,
  body: unknown,
  handlers: StreamHandlers = {},
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
    signal,
  });

  if (!res.ok || !res.body) {
    let code = `http_${res.status}`;
    let message = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data?.error) {
        code = data.error.code ?? code;
        message = data.error.message ?? message;
      }
    } catch { /* not JSON */ }
    handlers.onError?.(code, message);
    return { error: code, message };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done: Record<string, unknown> = {};

  for (;;) {
    const { value, done: readerDone } = await reader.read();
    if (readerDone) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const rawEvent of events) {
      const dataLine = rawEvent
        .split("\n")
        .find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice(5).trim();
      if (!json) continue;
      let evt: Record<string, unknown>;
      try {
        evt = JSON.parse(json);
      } catch {
        continue; // tolerate keep-alive or comment frames
      }
      const type = evt.type as string;
      if (type === "delta" && handlers.onDelta) {
        handlers.onDelta(String(evt.content ?? ""));
      } else if (type === "done") {
        done = evt;
        handlers.onDone?.(evt);
      } else if (type === "error") {
        handlers.onError?.(
          String(evt.code ?? "error"),
          String(evt.message ?? "Stream error"),
        );
        done = { error: String(evt.code ?? "error"), message: String(evt.message ?? "") };
      }
    }
  }
  return done;
}

export function providerName(cfg: string): string {
  return cfg.replace(/^https?:\/\//, "").slice(0, 40);
}
