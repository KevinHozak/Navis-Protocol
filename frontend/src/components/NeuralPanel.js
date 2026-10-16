import { useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import { apiFetch } from '@/lib/desktopApi';

const MarkdownRenderer = dynamic(() => import('./MarkdownRenderer'), { ssr: false });

export default function NeuralPanel({ persona }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [providerError, setProviderError] = useState(null);
  const abortRef = useRef(null);

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
  };

  const sendMessage = async (textOverride) => {
    const text = typeof textOverride === 'string' ? textOverride : input;
    if (!text.trim() || loading) return;
    const userMsg = text.trim();
    if (typeof textOverride !== 'string') setInput('');
    setProviderError(null);
    const newMsgs = [...messages, { role: 'user', content: userMsg }];
    setMessages(newMsgs);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await apiFetch('/api/neural/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, history: messages, persona }),
        signal: controller.signal,
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setMessages([...newMsgs, { role: 'assistant', content: data.response }]);
        setProviderError(null);
      } else {
        const errorMsg = data.detail || data.message || 'Error connecting to Neural Bridge.';
        setProviderError({ message: errorMsg, lastMsg: userMsg });
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setMessages([...newMsgs, { role: 'assistant', content: '_Transmission cancelled by Keeper._' }]);
      } else {
        setProviderError({ message: err.message || 'Connection failed.', lastMsg: userMsg });
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  return (
    <div className="flex flex-col h-full min-h-[60vh] bg-zinc-950/80 border border-white/10 rounded-xl overflow-hidden backdrop-blur-md shadow-2xl">
      {/* Header */}
      <div className="bg-zinc-900/80 px-4 py-3 border-b border-white/10 flex items-center gap-3">
        <span className="text-lg">🧠</span>
        <div>
          <p className="text-xs font-bold text-accent uppercase tracking-[0.2em]">Neural Bridge</p>
          {persona && (
            <p className="text-[10px] text-white/50 uppercase tracking-widest">
              Persona: <span className="text-amber-400 font-bold">{persona}</span>
            </p>
          )}
        </div>
        <div className="ml-auto w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-[0_0_6px_rgba(74,222,128,0.6)]" />
      </div>

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {providerError && (
          <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-lg text-red-200 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span>⚠️</span>
              <span>{providerError.message}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => sendMessage(providerError.lastMsg)}
                className="px-2.5 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-bold rounded text-[10px] uppercase tracking-wider transition-colors"
              >
                Retry
              </button>
              <button
                onClick={() => setProviderError(null)}
                className="text-red-400/60 hover:text-red-300 text-xs px-1"
              >
                ✕
              </button>
            </div>
          </div>
        )}
        {messages.length === 0 && (
          <div className="text-center mt-16">
            <p className="text-white/20 text-xs uppercase tracking-widest font-mono">
              {persona
                ? `${persona} is listening. Speak freely, Keeper.`
                : 'Awaiting your query, Keeper.'}
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed shadow-md ${
              msg.role === 'user'
                ? 'bg-accent/20 border border-accent/30 text-white'
                : 'bg-zinc-800/80 border border-white/10 text-white/85'
            }`}>
              {msg.role === 'assistant' ? (
                <>
                  {persona && (
                    <p className="text-[9px] text-amber-400/70 uppercase tracking-widest font-bold mb-1">{persona}</p>
                  )}
                  <MarkdownRenderer content={msg.content} />
                </>
              ) : (
                <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center justify-between bg-zinc-800/80 border border-white/10 rounded-lg px-4 py-2.5 max-w-[80%]">
            <div className="text-white/40 text-xs font-mono animate-pulse">
              {persona ? `${persona} is thinking...` : 'Connecting to Neural Bridge...'}
            </div>
            <button
              onClick={handleCancel}
              className="text-[10px] font-mono text-zinc-400 hover:text-zinc-200 uppercase tracking-widest px-2 py-0.5 rounded bg-white/5 border border-white/10 ml-3"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Input Bar */}
      <div className="p-3 bg-zinc-900/80 border-t border-white/10 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          disabled={loading}
          placeholder={persona ? `Speak to ${persona}...` : 'Transmit message...'}
          className="flex-1 bg-zinc-950 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 focus:outline-none focus:border-accent/60 transition-colors"
        />
        <button
          onClick={() => sendMessage()}
          disabled={loading || !input.trim()}
          className="px-4 py-2 bg-accent/20 hover:bg-accent/30 disabled:bg-zinc-800 disabled:text-white/20 text-accent border border-accent/30 font-bold rounded-lg text-xs uppercase tracking-widest transition-all"
        >
          Send
        </button>
      </div>
    </div>
  );
}
