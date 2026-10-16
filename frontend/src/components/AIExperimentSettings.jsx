"use client";

import React, { useCallback, useEffect, useState } from "react";
import { apiFetch, isTauriRuntime } from "../lib/desktopApi";

const EMPTY = { enabled: false, allow_vault_content: false, monthly_budget_usd: 1 };

export default function AIExperimentSettings() {
  const nativeRuntime = isTauriRuntime();
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(EMPTY);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (nativeRuntime) {
      setMessage("Native Tauri has no hosted AI or experiment-accounting adapter; online generation stays unavailable here.");
      return;
    }
    try {
      const response = await apiFetch("/api/ai/experiments");
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load AI diagnostics.");
      setStatus(data);
      setSettings({
        enabled: data.enabled,
        allow_vault_content: data.allow_vault_content,
        monthly_budget_usd: data.monthly_budget_usd || 1,
      });
    } catch (error) {
      setMessage(error.message);
    }
  }, [nativeRuntime]);

  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    setBusy(true);
    setMessage("");
    try {
      const response = await apiFetch("/api/ai/experiments", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save AI settings.");
      setStatus(data);
      setMessage("AI experiment settings saved.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border border-cyan-400/20 bg-zinc-950/90 p-5 backdrop-blur-md space-y-4">
      <div>
        <h4 className="text-sm font-bold uppercase tracking-widest text-cyan-300">Online AI Experiments</h4>
        <p className="mt-1 text-xs text-white/50">Local Ollama remains the default. Online use is off until you enable it here.</p>
      </div>
      <label className="flex items-start gap-3 text-sm text-white/80">
        <input type="checkbox" disabled={nativeRuntime} checked={settings.enabled} onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })} />
        <span>Enable budgeted Gemini for interactive AI requests</span>
      </label>
      <label className="flex items-start gap-3 text-sm text-white/80">
        <input type="checkbox" disabled={nativeRuntime} checked={settings.allow_vault_content} onChange={(event) => setSettings({ ...settings, allow_vault_content: event.target.checked })} />
        <span>Allow Vault-derived text in online requests <span className="text-amber-300">(sensitive content)</span></span>
      </label>
      <label className="block space-y-1 text-xs text-white/60">
        Monthly hard budget (USD)
        <input type="number" disabled={nativeRuntime} min="0.01" max="100" step="0.01" value={settings.monthly_budget_usd} onChange={(event) => setSettings({ ...settings, monthly_budget_usd: Number(event.target.value) })} className="block w-40 rounded border border-white/10 bg-black px-3 py-2 font-mono text-white disabled:opacity-50" />
      </label>
      {status && <div className="rounded border border-white/10 bg-black/40 p-3 text-xs text-white/60">
        <div>Provider/model: {status.provider} / {status.model}</div>
        <div>Key configured: {status.api_key_available ? "yes" : "no"} · Month-to-date reserved: ${Number(status.month_to_date_reserved_usd).toFixed(4)} of ${Number(status.monthly_budget_usd).toFixed(2)} USD</div>
        <div>Per request: ≤{status.input_limit_chars.toLocaleString()} characters, ≤{status.output_limit_tokens.toLocaleString()} output tokens · resets monthly in UTC</div>
        <div>Price review: {status.price_review_date}{status.price_review_stale ? " · stale, online calls blocked" : ""} · prompts are never stored in usage records</div>
      </div>}
      <button disabled={busy || nativeRuntime} onClick={save} className="rounded border border-cyan-400/40 px-4 py-2 text-xs font-bold uppercase tracking-widest text-cyan-200 hover:bg-cyan-400/10 disabled:opacity-50">{busy ? "Saving…" : "Save AI Controls"}</button>
      {message && <p role="status" className="text-xs text-white/60">{message}</p>}
    </section>
  );
}
