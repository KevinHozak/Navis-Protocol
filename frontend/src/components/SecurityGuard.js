'use client';
import { useState, useEffect } from 'react';
import { apiFetch, isTauriRuntime } from '../lib/desktopApi';

export default function SecurityGuard({ children }) {
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [inputKey, setInputKey] = useState('');
  const [isError, setIsError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function checkAuth() {
      // Native desktop uses local Tauri IPC; web security gate applies to HTTP compatibility mode
      if (isTauriRuntime()) {
        if (active) {
          setIsAuthorized(true);
          setIsLoading(false);
        }
        return;
      }

      try {
        const savedKey =
          typeof window !== 'undefined'
            ? sessionStorage.getItem('vanguard_key') || localStorage.getItem('vanguard_key')
            : null;

        const res = await apiFetch('/api/auth/status');
        if (!res.ok) {
          throw new Error('Status query failed');
        }
        const data = await res.json();

        if (!data.auth_required) {
          // Local loopback dev mode where auth is not required
          if (active) {
            setIsAuthorized(true);
            setIsLoading(false);
          }
          return;
        }

        // Auth is required: verify saved key if present
        if (savedKey) {
          const verifyRes = await apiFetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: savedKey }),
          });
          if (verifyRes.ok) {
            if (active) {
              setIsAuthorized(true);
              setIsLoading(false);
            }
            return;
          }
          // Saved key is invalid
          if (typeof window !== 'undefined') {
            sessionStorage.removeItem('vanguard_key');
            localStorage.removeItem('vanguard_key');
          }
        }

        if (active) {
          setIsAuthorized(false);
          setIsLoading(false);
        }
      } catch {
        // Fallback for loopback dev if backend is offline or starting up
        if (
          typeof window !== 'undefined' &&
          (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ) {
          if (active) {
            setIsAuthorized(true);
            setIsLoading(false);
          }
          return;
        }
        if (active) {
          setIsAuthorized(false);
          setIsLoading(false);
        }
      }
    }

    checkAuth();
    return () => {
      active = false;
    };
  }, []);

  const handleAuthorize = async (e) => {
    e.preventDefault();
    if (!inputKey.trim()) {
      setIsError(true);
      setTimeout(() => setIsError(false), 2000);
      return;
    }

    try {
      const res = await apiFetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: inputKey.trim() }),
      });

      if (res.ok) {
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('vanguard_key', inputKey.trim());
          localStorage.setItem('vanguard_key', inputKey.trim());
        }
        setIsAuthorized(true);
        setIsError(false);
      } else {
        setIsError(true);
        setTimeout(() => setIsError(false), 2000);
      }
    } catch {
      setIsError(true);
      setTimeout(() => setIsError(false), 2000);
    }
  };

  if (isLoading) return null;

  if (!isAuthorized) {
    return (
      <div className="fixed inset-0 z-[9999] bg-[#050505] flex items-center justify-center p-6">
        <div className="absolute inset-0 opacity-20 pointer-events-none" 
             style={{ backgroundImage: "url('/assets/textures/canaan_house.png')", backgroundSize: 'cover' }} />
        
        <div className="w-full max-w-md glass-dark p-10 rounded border border-white/10 shadow-2xl relative z-10 text-center space-y-8">
          <div className="space-y-2">
            <div className="text-accent text-5xl mb-4">🛡️</div>
            <h1 className="text-2xl font-bold text-white uppercase tracking-[0.3em]">Vanguard Lock</h1>
            <p className="text-[10px] text-white/40 uppercase tracking-widest">Unauthorized Access Detected | Primary Authority Required</p>
          </div>

          <form onSubmit={handleAuthorize} className="space-y-6">
            <div className="space-y-2 text-left">
              <label className="text-[9px] text-accent uppercase tracking-widest ml-1">Enter Security Key</label>
              <input 
                type="password"
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                className={`w-full bg-black/60 border ${isError ? 'border-red-500/50' : 'border-white/10'} p-4 rounded text-white focus:outline-none focus:border-accent/50 transition-all font-mono text-center tracking-[0.5em]`}
                placeholder="••••••••"
              />
              {isError && <p className="text-[8px] text-red-400 uppercase tracking-widest text-center animate-pulse">Invalid Signal | Access Denied</p>}
            </div>

            <button 
              type="submit"
              className="w-full py-4 bg-accent/10 hover:bg-accent/20 border border-accent/40 rounded text-accent text-xs font-bold uppercase tracking-[0.3em] transition-all"
            >
              Authorize Terminal
            </button>
          </form>

          <div className="pt-4 border-t border-white/5 text-[8px] text-white/20 uppercase tracking-widest leading-relaxed">
            Bridge Encryption Active <br />
            Codex Realm Monitoring Enabled
          </div>
        </div>
      </div>
    );
  }

  return children;
}
