import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, streamSse } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { Conversation, Message, TutorMode } from "../api/types";
import { Markdown } from "../components/Markdown";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Select,
  Spinner,
} from "../components/ui";

export default function Tutor() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { data: health } = useApi<{ demo_mode: boolean }>("/health");

  const { data: modesData } = useApi<{ modes: TutorMode[] }>("/tutor/modes");
  const modes = modesData?.modes ?? [];

  const { data: convData, refresh: refreshConvs } =
    useApi<{ conversations: Conversation[] }>("/conversations");

  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("learn");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);

  // Deep-linked from an exercise ("Ask the AI tutor").
  const exerciseParam = Number(params.get("exercise"));

  const ensureConversation = useCallback(
    async (initialMode: string): Promise<number> => {
      const conv = await api.post<Conversation>("/conversations", {
        mode: initialMode,
        title: "New chat",
      });
      setConversationId(conv.id);
      setMessages([]);
      refreshConvs();
      return conv.id;
    },
    [refreshConvs],
  );

  async function openConversation(id: number) {
    abortRef.current?.abort();
    setStreaming(false);
    setStreamText("");
    const detail = await api.get<Conversation & { messages: Message[] }>(
      `/conversations/${id}`,
    );
    setConversationId(id);
    setMessages(detail.messages);
    setMode(detail.mode ?? "learn");
    setError(null);
  }

  async function send() {
    const content = input.trim();
    if (!content || streaming) return;
    setInput("");
    setError(null);

    let cid = conversationId;
    if (cid === null) {
      setCreating(true);
      try {
        cid = await ensureConversation(mode);
      } catch (e) {
        setError((e as Error).message);
        setCreating(false);
        return;
      }
      setCreating(false);
    }
    if (cid === null) return;

    const userMsg: Message = {
      id: -Date.now(),
      role: "user",
      content,
      mode,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);
    setStreaming(true);
    setStreamText("");

    const controller = new AbortController();
    abortRef.current = controller;

    await streamSse(
      `/conversations/${cid}/chat`,
      { content, mode },
      {
        onDelta: (piece) => setStreamText((t) => t + piece),
        onDone: () => undefined,
        onError: (code, message) => setError(message),
      },
      controller.signal,
    );

    setStreaming(false);
    setStreamText("");
    abortRef.current = null;
    // Reload the conversation from the server (authoritative message list).
    try {
      const detail = await api.get<Conversation & { messages: Message[] }>(
        `/conversations/${cid}`,
      );
      setMessages(detail.messages);
      refreshConvs();
    } catch {
      refreshConvs();
    }
  }

  async function retryLast() {
    if (conversationId === null || streaming) return;
    setStreaming(true);
    setStreamText("");
    const controller = new AbortController();
    abortRef.current = controller;
    await streamSse(
      `/conversations/${conversationId}/retry`,
      {},
      {
        onDelta: (piece) => setStreamText((t) => t + piece),
        onError: (code, message) => setError(message),
      },
      controller.signal,
    );
    setStreaming(false);
    setStreamText("");
    abortRef.current = null;
    const detail = await api
      .get<Conversation & { messages: Message[] }>(
        `/conversations/${conversationId}`,
      )
      .catch(() => null);
    if (detail) setMessages(detail.messages);
    refreshConvs();
  }

  async function deleteConversation(id: number) {
    await api.del(`/conversations/${id}`);
    if (id === conversationId) {
      setConversationId(null);
      setMessages([]);
    }
    refreshConvs();
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText]);

  // Prefill from the exercise deep-link.
  useEffect(() => {
    if (Number.isFinite(exerciseParam) && exerciseParam > 0) {
      api
        .get<{ title: string }>(`/exercises/${exerciseParam}`)
        .then((ex) =>
          setInput(
            `I'm working on the exercise "${ex.title}". I don't want the ` +
              `answer - just a hint about the concept I might be missing.`,
          ),
        )
        .catch(() => undefined);
    }
  }, [exerciseParam]);

  const conversations = convData?.conversations ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
      {/* Conversations */}
      <aside className="space-y-2">
        <Button
          className="w-full"
          onClick={async () => {
            try {
              await ensureConversation(mode);
              setError(null);
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          + New chat
        </Button>
        <ul className="space-y-1">
          {conversations.map((c) => (
            <li key={c.id} className="group flex items-center gap-1">
              <button
                onClick={() => openConversation(c.id)}
                className={`min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surfaceHover ${
                  c.id === conversationId ? "bg-primary/10 text-primary" : ""
                }`}
              >
                <span className="block truncate">{c.title}</span>
                <span className="block truncate text-xs text-muted">
                  {c.message_count} messages
                </span>
              </button>
              <button
                onClick={() => deleteConversation(c.id)}
                className="shrink-0 rounded px-1 text-xs text-muted opacity-0 hover:text-danger group-hover:opacity-100"
                aria-label={`Delete chat ${c.title}`}
                title="Delete conversation"
              >
                ×
              </button>
            </li>
          ))}
          {conversations.length === 0 && (
            <li className="text-xs text-muted">
              No conversations yet. Start a new chat above.
            </li>
          )}
        </ul>
      </aside>

      {/* Chat */}
      <section className="flex min-h-[70vh] flex-col">
        {/* Mode selector */}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">Teaching mode:</span>
          <Select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            className="w-auto"
            aria-label="Teaching mode"
          >
            {modes.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </Select>
          <span className="hidden text-xs text-muted sm:inline">
            {modes.find((m) => m.id === mode)?.description}
          </span>
        </div>

        <Card className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && !streaming && (
            <EmptyState
              title="Ask any programming question"
              description="The tutor teaches step by step: it explains new terms, uses small examples, and turns your mistakes into lessons. Choose a teaching mode above to change how it behaves."
              action={
                <Link to="/learn/python/what-is-programming">
                  <Button size="sm" variant="outline">
                    Start with lesson 1
                  </Button>
                </Link>
              }
            />
          )}

          {messages.map((m) => (
            <div
              key={m.id}
              className={m.role === "user" ? "flex justify-end" : ""}
            >
              <div
                className={
                  (m.role === "user"
                    ? "max-w-[85%] rounded-xl rounded-br-sm bg-primary/15 px-3.5 py-2"
                    : "max-w-[92%] rounded-xl rounded-bl-sm border border-border px-3.5 py-2") +
                  " text-sm"
                }
              >
                {m.role === "assistant" ? (
                  <Markdown content={m.content} />
                ) : (
                  <p className="whitespace-pre-wrap">{m.content}</p>
                )}
              </div>
            </div>
          ))}

          {streaming && (
            <div className="max-w-[92%] rounded-xl rounded-bl-sm border border-border px-3.5 py-2 text-sm">
              {streamText ? (
                <Markdown content={streamText} />
              ) : (
                <span className="flex items-center gap-2 text-muted">
                  <Spinner /> the tutor is thinking...
                </span>
              )}
              <span className="ml-0.5 inline-block animate-pulse-dot">▍</span>
            </div>
          )}
          <div ref={messagesEnd} />
        </Card>

        {error && (
          <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-danger/40 bg-danger/5 px-3 py-2 text-sm">
            <span className="text-danger">{error}</span>
            {health && !health.demo_mode && (
              <Button size="sm" variant="outline" onClick={retryLast}>
                Retry
              </Button>
            )}
          </div>
        )}

        {health?.demo_mode && (
          <p className="mt-2 text-xs text-warning">
            No AI provider is configured, so the tutor cannot answer here.{" "}
            <Link to="/settings" className="underline">
              Add a provider in Settings
            </Link>{" "}
            - meanwhile all lessons and exercises work offline.
          </p>
        )}

        {/* Composer */}
        <div className="mt-3 flex items-end gap-2">
          <textarea
            className="input-base min-h-11"
            rows={2}
            placeholder="Ask about any concept, paste code with an error, or request practice..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          {streaming ? (
            <Button variant="danger" onClick={stop}>
              Stop
            </Button>
          ) : (
            <Button onClick={send} disabled={!input.trim() || creating}>
              {creating ? "..." : "Send"}
            </Button>
          )}
        </div>
        <p className="mt-1 text-xs text-muted">
          Enter sends · Shift+Enter adds a newline
          {conversationId !== null && " · answers are saved to this chat"}
        </p>

        {messages.length === 0 && (
          <div className="mt-4">
            <Badge>Suggested first questions</Badge>
            <div className="mt-2 flex flex-wrap gap-2">
              {[
                "I'm brand new to coding - where should I start?",
                "Explain variables like I'm 10.",
                "My program says SyntaxError: invalid syntax. What does that mean?",
                "Give me a practice exercise on loops (a hint only).",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:text-fg"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
