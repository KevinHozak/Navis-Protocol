"use client";
import { useEffect, useState } from 'react';

export function timestamp(value) {
  if (typeof value !== 'string') return 'Unknown';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value} (date only; timezone unknown)`;
  if (!/(Z|[+-]\d{2}:\d{2})$/i.test(value) || !Number.isFinite(Date.parse(value))) return 'Unknown';
  return new Date(value).toISOString().replace('T', ' ').replace('Z', ' UTC');
}

export default function ReadFreshness({ label, pending, lastRead, error, sourceLabel, sourceTime, onRetry }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const age = lastRead ? Math.max(0, Math.floor((now - Date.parse(lastRead)) / 60000)) : null;
  return <div role="status" className="shrink-0 flex flex-wrap items-center gap-x-3 gap-y-1 border border-white/10 bg-zinc-950/90 px-4 py-2 text-xs text-zinc-300 backdrop-blur-md">
    <span className={error ? 'text-amber-200' : 'text-cyan-200'}>{label}: {pending ? 'Refreshing…' : error ? 'Refresh failed' : lastRead ? 'Read complete' : 'Not read'}</span>
    <span>Last successful read: {timestamp(lastRead)}{age !== null ? ` · ${age} min ago${error || pending ? ' · retained data' : ''}` : ''}</span>
    <span>{sourceLabel}: {timestamp(sourceTime)} · Input freshness unknown</span>
    <button type="button" disabled={pending} onClick={onRetry} className="text-cyan-300 underline disabled:opacity-40">{error ? 'Retry refresh' : 'Refresh'}</button>
  </div>;
}
