import { memo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { cx } from "../lib/utils";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="rounded border border-border bg-surface px-2 py-1 text-xs text-muted hover:text-fg"
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function CodeBlock({ code, language }: { code: string; language?: string }) {
  return (
    <div className="not-prose my-3 overflow-hidden rounded-lg border border-border bg-bg">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5 text-xs text-muted">
        <span>{language ?? "code"}</span>
        <CopyButton text={code} />
      </div>
      <pre className="overflow-x-auto p-3 text-sm leading-relaxed">
        <code className={cx("language-" + (language ?? ""))}>{code}</code>
      </pre>
    </div>
  );
}

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mb-2 mt-5 text-xl font-semibold">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-5 text-lg font-semibold">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-4 text-base font-semibold">{children}</h3>
  ),
  p: ({ children }) => <p className="my-2 text-sm leading-6">{children}</p>,
  ul: ({ children }) => (
    <ul className="my-2 list-disc space-y-1 pl-5 text-sm leading-6">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 list-decimal space-y-1 pl-5 text-sm leading-6">{children}</ol>
  ),
  code: ({
    className,
    children,
  }: {
    className?: string;
    children?: ReactNode;
  }) => {
    const text = String(children ?? "");
    const match = /language-(\w+)/.exec(className ?? "");
    const isInline = !match && !text.includes("\n");
    if (isInline) {
      return (
        <code className="rounded border border-border bg-surface px-1.5 py-0.5 text-[0.85em] text-primary">
          {children}
        </code>
      );
    }
    return (
      <CodeBlock code={text.replace(/\n$/, "")} language={match?.[1]} />
    );
  },
  pre: ({ children }) => <>{children}</>,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border px-3 py-1.5 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-3 py-1.5">{children}</td>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-primary pl-3 italic text-muted">
      {children}
    </blockquote>
  ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer"
      className="text-primary underline hover:no-underline">
      {children}
    </a>
  ),
};

export const Markdown = memo(function Markdown({ content }: { content: string }) {
  return (
    <div className="text-sm text-fg">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
