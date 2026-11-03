"use client";

import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '@/lib/desktopApi';

const Link = ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-cyan-300 underline underline-offset-4 hover:text-cyan-100">{children}</a>;

export default function ProjectsView() {
  const [data, setData] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const request = useRef(0);
  const refresh = async () => {
    const id = ++request.current;
    setPending(true);
    setError(null);
    // Do not display a previous account's private repositories during refresh.
    setData(null);
    try {
      const response = await apiFetch('/api/projects', { signal: AbortSignal.timeout(35000) });
      const value = await response.json();
      if (!response.ok) throw new Error(value.detail || 'GitHub overview unavailable.');
      if (!Array.isArray(value.repositories) || typeof value.refreshed_at !== 'string') throw new Error('Invalid repository overview.');
      if (id === request.current) setData(value);
    } catch (failure) {
      if (id === request.current) setError(failure.message || 'GitHub overview unavailable.');
    } finally {
      if (id === request.current) setPending(false);
    }
  };
  useEffect(() => { refresh(); return () => { request.current += 1; }; }, []);
  return <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-auto space-y-5 text-white">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-bold tracking-widest">PROJECTS</h1>
      <button onClick={refresh} disabled={pending} className="rounded border border-cyan-400/30 bg-zinc-950/90 px-4 py-2 text-cyan-300 disabled:opacity-50">{pending ? 'Loading…' : 'Refresh'}</button>
    </header>
    {pending && <p role="status">Loading repositories…</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {data && <>
      <p className="text-sm text-white/60">{data.account} · Refreshed {new Date(data.refreshed_at).toLocaleString()}</p>
      {data.partial && <p role="status" className="text-amber-300">Some repository data is unavailable. Available results are shown.</p>}
      {data.limited && <p className="text-amber-300">Showing up to {data.limit} recently pushed repositories. More repositories are available on GitHub.</p>}
      {!data.repositories.length && <p>No accessible repositories found.</p>}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {data.repositories.map(repo => <article key={repo.name} className="rounded-xl border border-white/10 bg-zinc-950/90 p-5 space-y-3 backdrop-blur-md">
          <div className="flex justify-between gap-3"><h2 className="font-bold break-all"><Link href={repo.url}>{repo.name}</Link></h2><span className="text-xs text-white/60">{repo.visibility}{repo.archived ? ' · Archived' : ''}</span></div>
          {repo.description && <p className="text-sm text-white/70">{repo.description}</p>}
          <div className="flex gap-5 text-sm"><Link href={`${repo.url}/issues`}>Issues: {repo.issues ?? 'Unavailable'}</Link><Link href={`${repo.url}/pulls`}>PRs: {repo.pull_requests ?? 'Unavailable'}</Link><Link href={`${repo.url}/commits`}>Commits</Link></div>
          {repo.commit ? <p className="text-sm"><Link href={repo.commit.url}>{repo.commit.summary}</Link><br /><time className="text-white/50" dateTime={repo.commit.date}>{new Date(repo.commit.date).toLocaleString()}</time></p> : <p className="text-sm text-white/50">No default-branch commit available.</p>}
        </article>)}
      </div>
    </>}
  </motion.section>;
}
