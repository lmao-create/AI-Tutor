import { useState } from "react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import type { Preferences, ProviderView } from "../api/types";
import { Markdown } from "../components/Markdown";
import {
  Badge,
  Button,
  Card,
  Label,
  Select,
  useToast,
} from "../components/ui";

const PRESETS = [
  {
    label: "NVIDIA NIM (build.nvidia.com)",
    provider_name: "NVIDIA NIM",
    base_url: "https://integrate.api.nvidia.com/v1",
    model: "meta/llama-3.3-70b-instruct",
  },
  {
    label: "OpenAI",
    provider_name: "OpenAI",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
  },
  {
    label: "Groq",
    provider_name: "Groq",
    base_url: "https://api.groq.com/openai/v1",
    model: "llama-3.3-70b-versatile",
  },
  {
    label: "OpenRouter",
    provider_name: "OpenRouter",
    base_url: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4o-mini",
  },
  {
    label: "Ollama (local, no key needed)",
    provider_name: "Ollama",
    base_url: "http://127.0.0.1:11434/v1",
    model: "llama3.1",
  },
];

export default function SettingsPage() {
  const { data: provider, refresh: refreshProvider } =
    useApi<ProviderView>("/settings/provider");
  const { data: prefs, refresh: refreshPrefs } =
    useApi<Preferences>("/settings/preferences");
  const { toast } = useToast();

  const [providerName, setProviderName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
    key: "ok" | "bad";
  } | null>(null);

  function fillPreset(index: number) {
    const p = PRESETS[index];
    setProviderName(p.provider_name);
    setBaseUrl(p.base_url);
    setModel(p.model);
  }

  async function saveProvider() {
    setSaving(true);
    try {
      await api.put("/settings/provider", {
        provider_name: providerName || "Custom provider",
        base_url: baseUrl,
        model: model,
        // Send the key only when it was actually typed in. An empty string
        // clears a stored key; omitting keeps the existing one.
        ...(apiKey.trim() === "" ? {} : { api_key: apiKey }),
      });
      setApiKey("");
      toast("Provider settings saved.", "success");
      refreshProvider();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Save failed.", "danger");
    } finally {
      setSaving(false);
    }
  }

  async function testProvider() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post<{
        ok: boolean;
        message: string;
      }>("/settings/provider/test", {
        provider_name: providerName || undefined,
        base_url: baseUrl || undefined,
        model: model || undefined,
        api_key: apiKey.trim() || undefined,
      });
      setTestResult({ ok: res.ok, message: res.message, key: res.ok ? "ok" : "bad" });
    } catch (e) {
      setTestResult({
        ok: false,
        key: "bad",
        message: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setTesting(false);
    }
  }

  async function clearProvider() {
    try {
      await api.del("/settings/provider");
      toast("Provider configuration removed - demo mode.", "info");
      refreshProvider();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not clear.", "danger");
    }
  }

  async function savePref(next: Partial<Preferences>) {
    try {
      await api.put("/settings/preferences", next);
      toast("Preferences saved.", "success");
      refreshPrefs();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Save failed.", "danger");
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted">
          Configure an AI provider to unlock the tutor chat, explainer and
          debugging assistant. Everything works offline without one.
        </p>
      </header>

      {/* AI provider */}
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">AI provider</h2>
          <Badge tone={provider?.configured ? "success" : "warning"}>
            {provider?.configured
              ? `Connected via ${provider.source === "env" ? "environment file" : "Settings"}`
              : "Demo mode (no provider)"}
          </Badge>
        </div>

        {provider?.configured ? (
          <div className="rounded-lg border border-border bg-bg p-3 text-sm">
            <p>
              <strong>{provider.provider_name}</strong> · model{" "}
              <code className="text-primary">{provider.model}</code>
            </p>
            <p className="mt-1 text-xs text-muted">
              {provider.base_url} · key{" "}
              <code>{provider.key_masked ?? "not set"}</code> (masked - the real
              key never leaves the server)
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted">
            No provider is configured. AI features are disabled and everything
            else runs offline. Add one below (NVIDIA NIM is pre-filled as an
            example - create a free key at build.nvidia.com).
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p, i) => (
            <Button
              key={p.label}
              variant="outline"
              size="sm"
              onClick={() => fillPreset(i)}
            >
              {p.label}
            </Button>
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="pn">Provider name (display only)</Label>
            <input
              id="pn"
              className="input-base"
              value={providerName}
              onChange={(e) => setProviderName(e.target.value)}
              placeholder="NVIDIA NIM"
            />
          </div>
          <div>
            <Label htmlFor="mu">Model</Label>
            <input
              id="mu"
              className="input-base"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="meta/llama-3.3-70b-instruct"
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="bu">API base URL (OpenAI-compatible)</Label>
            <input
              id="bu"
              className="input-base"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://integrate.api.nvidia.com/v1"
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="ak">API key</Label>
            <input
              id="ak"
              type="password"
              className="input-base"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={
                provider?.configured
                  ? "Leave blank to keep the stored key"
                  : "Paste your key (stored server-side only)"
              }
            />
            <p className="mt-1 text-xs text-muted">
              The key is stored in a local secrets file on the backend machine
              only. It is never sent to the browser and never included in AI
              messages. Type an empty value and save to remove it.
            </p>
          </div>
        </div>

        {testResult && (
          <p
            className={
              "text-sm " +
              (testResult.ok ? "text-success" : "text-danger")
            }
          >
            {testResult.ok ? "✓ " : "✗ "}
            {testResult.message}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button onClick={saveProvider} disabled={saving || !baseUrl || !model}>
            {saving ? "Saving..." : "Save configuration"}
          </Button>
          <Button
            variant="outline"
            onClick={testProvider}
            disabled={testing || !baseUrl || !model}
          >
            {testing ? "Testing..." : "Test connection"}
          </Button>
          {provider?.configured && (
            <Button variant="ghost" onClick={clearProvider}>
              Remove provider
            </Button>
          )}
        </div>
      </Card>

      {/* Preferences */}
      <Card className="space-y-3">
        <h2 className="text-sm font-semibold">Preferences</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="tutor-mode">Default tutor mode</Label>
            <Select
              id="tutor-mode"
              value={prefs?.default_tutor_mode ?? "learn"}
              onChange={(e) =>
                savePref({ default_tutor_mode: e.target.value } as
                  Partial<Preferences>)
              }
            >
              <option value="learn">Learn</option>
              <option value="practice">Practice</option>
              <option value="debug">Debug</option>
              <option value="project">Project</option>
              <option value="interview">Interview</option>
              <option value="explain">Explain</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="course">Default learning path</Label>
            <Select
              id="course"
              value={prefs?.active_course ?? "python"}
              onChange={(e) =>
                savePref({ active_course: e.target.value } as
                  Partial<Preferences>)
              }
            >
              <option value="python">Python for Beginners</option>
            </Select>
          </div>
        </div>
        <p className="text-xs text-muted">
          Theme is toggled with the sun/moon button in the header and is saved
          on this machine.
        </p>
      </Card>

      {/* Security notes */}
      <Card className="space-y-2">
        <h2 className="text-sm font-semibold">Security notes</h2>
        <Markdown
          content={`- The API key lives only in the backend's local secrets file or the environment. It is **never** exposed to the browser, included in any API response, or pasted into AI messages.
- Student code executes in a separate process sandbox: stripped environment, scratch directory, network modules blocked, hard time limit, memory cap.
- Rate limits protect the expensive endpoints (AI calls 20/min, code runs 40/min).
- Full details are in \`docs/SECURITY.md\` in the project folder.`}
        />
      </Card>
    </div>
  );
}
