"use client";

import { useEffect, useState } from 'react';
import { isTauriRuntime, startupDiagnostics } from '@/lib/desktopApi';

export default function DesktopDiagnostics() {
  const [state, setState] = useState(null);

  useEffect(() => {
    if (!isTauriRuntime()) return undefined;
    let active = true;
    startupDiagnostics()
      .then((result) => {
        if (!active) return;
        const failures = (result.checks || [])
          .filter((check) => !check.ok && check.severity === 'error')
          .map((check) => `${check.label}: ${check.message}`);
        setState({
          ok: result.overall_ok !== false,
          message: failures.length
            ? `Vault diagnostic · ${failures.join(' · ')}`
            : `IPC online · v${result.version}`,
        });
      })
      .catch((error) => {
        if (active) setState({ ok: false, message: `IPC unavailable · ${error.message}` });
      });
    return () => { active = false; };
  }, []);

  if (!state) return null;
  return (
    <div role="status" className={`fixed bottom-3 left-3 z-50 max-w-sm rounded border px-3 py-2 font-mono text-[10px] shadow-lg backdrop-blur-md ${state.ok ? 'border-cyan-400/30 bg-cyan-950/80 text-cyan-200' : 'border-red-400/40 bg-red-950/90 text-red-200'}`}>
      {state.message}
    </div>
  );
}
