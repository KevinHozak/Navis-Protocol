"use client";

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { apiFetch, isTauriRuntime, vaultAssetUrl } from '../lib/desktopApi';
import { conversationError, conversationMessage } from '../lib/conversationError';
import NativeCapabilityNotice from './NativeCapabilityNotice';

async function streamResponse(response, onChunk) {
  if (!response.body?.getReader) {
    onChunk(await response.text());
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}

const getSpeakerTheme = (name) => {
  const normalized = (name || '').trim().toLowerCase();
  if (normalized.includes('arwen')) {
    return {
      textAccent: 'text-sky-400',
      borderAccent: 'border-sky-500/30',
      bgAccent: 'bg-sky-950/40 backdrop-blur-sm',
      glow: 'shadow-[0_0_12px_rgba(56,189,248,0.15)]',
      textColor: 'text-sky-100/90'
    };
  }
  if (normalized.includes('ahri')) {
    return {
      textAccent: 'text-pink-400',
      borderAccent: 'border-pink-500/30',
      bgAccent: 'bg-pink-950/40 backdrop-blur-sm',
      glow: 'shadow-[0_0_12px_rgba(244,114,182,0.15)]',
      textColor: 'text-pink-100/90'
    };
  }
  if (normalized.includes('firiona')) {
    return {
      textAccent: 'text-emerald-400',
      borderAccent: 'border-emerald-500/30',
      bgAccent: 'bg-emerald-950/40 backdrop-blur-sm',
      glow: 'shadow-[0_0_12px_rgba(52,211,153,0.15)]',
      textColor: 'text-emerald-100/90'
    };
  }
  if (normalized.includes('keeper') || normalized.includes('kevin')) {
    return {
      textAccent: 'text-amber-400',
      borderAccent: 'border-amber-500/30',
      bgAccent: 'bg-amber-950/40 backdrop-blur-sm',
      glow: 'shadow-[0_0_12px_rgba(251,191,36,0.15)]',
      textColor: 'text-amber-100/90'
    };
  }
  // Deterministic fallback based on name hash
  let hash = 0;
  for (let i = 0; i < normalized.length; i++) {
    hash = normalized.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colorIndex = Math.abs(hash) % 4;
  const colors = [
    { textAccent: 'text-violet-400', borderAccent: 'border-violet-500/20', bgAccent: 'bg-violet-950/30 backdrop-blur-sm', glow: 'shadow-[0_0_12px_rgba(167,139,250,0.1)]', textColor: 'text-violet-100/90' },
    { textAccent: 'text-indigo-400', borderAccent: 'border-indigo-500/20', bgAccent: 'bg-indigo-950/30 backdrop-blur-sm', glow: 'shadow-[0_0_12px_rgba(129,140,248,0.1)]', textColor: 'text-indigo-100/90' },
    { textAccent: 'text-teal-400', borderAccent: 'border-teal-500/20', bgAccent: 'bg-teal-950/30 backdrop-blur-sm', glow: 'shadow-[0_0_12px_rgba(45,212,191,0.1)]', textColor: 'text-teal-100/90' },
    { textAccent: 'text-fuchsia-400', borderAccent: 'border-fuchsia-500/20', bgAccent: 'bg-fuchsia-950/30 backdrop-blur-sm', glow: 'shadow-[0_0_12px_rgba(232,121,249,0.1)]', textColor: 'text-fuchsia-100/90' }
  ];
  return colors[colorIndex];
};

const BanterMarkdown = ({ text, theme }) => {
  if (!text) return null;

  let cleanText = text.trim();
  if ((cleanText.startsWith('"') && cleanText.endsWith('"')) ||
      (cleanText.startsWith('“') && cleanText.endsWith('”'))) {
    cleanText = cleanText.slice(1, -1).trim();
  }

  // Pre-process thoughts [thought] -> HTML span
  const processed = cleanText.replace(/\[([^\]]+)\]/g, '<span class="text-white/40 italic text-[14px] mx-1">[$1]</span>');

  return (
    <div className={`warroom-markdown ${theme.textColor}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          p: ({node, ...props}) => <p className="mb-2 last:mb-0 leading-relaxed" {...props} />,
          em: ({node, ...props}) => <em className="text-emerald-400/80 italic font-mono text-[13px] mx-1">*{props.children}*</em>,
          strong: ({node, ...props}) => <strong className="font-bold text-white opacity-90" {...props} />,
          ul: ({node, ...props}) => <ul className="list-disc pl-4 mb-2 space-y-1" {...props} />,
          ol: ({node, ...props}) => <ol className="list-decimal pl-4 mb-2 space-y-1" {...props} />,
          li: ({node, ...props}) => <li className="pl-1" {...props} />,
          code: ({node, inline, className, children, ...props}) => 
            inline ? <code className="bg-black/30 px-1 py-0.5 rounded font-mono text-[12px]" {...props}>{children}</code>
                   : <pre className="bg-black/40 p-2 rounded my-2 overflow-x-auto font-mono text-[12px]"><code {...props}>{children}</code></pre>,
          a: ({node, ...props}) => <a className="text-accent hover:underline" target="_blank" rel="noopener noreferrer" {...props} />
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
};

export default function WarRoom() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [providerError, setProviderError] = useState(null);
  const scrollRef = useRef(null);
  const abortRef = useRef(null);

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
  };

  const loadHistory = async () => {
    setLoading(true);
    setProviderError(null);
    try {
      const res = await apiFetch('/api/neural/warroom/history');
      if (!res.ok) throw await conversationError(res, "Failed to load War Room history. Check the backend connection and retry.");
      const data = await res.json();
      if (!Array.isArray(data)) throw new Error("War Room history response is invalid. Retry loading history.");
      setMessages(data);
      if (data.length === 0) await handleSendSilent("/init", data);
    } catch (err) {
      setProviderError({ message: conversationMessage(err, 'Failed to load War Room history. Check the backend connection and retry.'), operation: 'history' });
    } finally {
      setLoading(false);
    }
  };

  // Load once on mount; retry uses the current render so it retains the draft.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadHistory(); }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleClear = async () => {
    if (!window.confirm("Are you sure you want to clear the War Room history?")) return;
    try {
      const res = await apiFetch('/api/neural/warroom/clear', { method: "POST" });
      if (!res.ok) throw await conversationError(res, "Failed to clear War Room history. Check the backend connection and retry.");
      setMessages([]);
      handleSendSilent("/init", []);
    } catch (err) {
      console.error("Failed to clear history:", err);
      setProviderError({ message: conversationMessage(err, "Failed to clear history. Check the backend connection and retry."), operation: 'clear' });
    }
  };

  const handleSendSilent = async (msgText, baseline = messages, requestId = crypto.randomUUID()) => {
    setLoading(true);
    setProviderError(null);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await apiFetch('/api/neural/warroom/chat', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msgText, request_id: requestId }),
        signal: controller.signal,
      });
      if (!res.ok) {
        throw await conversationError(res, "War Room initialization failed. Verify Python dependencies, start Ollama, and check the configured model.");
      }
      
      let assistantResponse = "";
      setMessages(prev => [...prev, { role: 'assistant', content: "" }]);
      
      await streamResponse(res, (chunk) => {
        assistantResponse += chunk;
        const cleanResponse = assistantResponse.replace(/<\|im_end\|>/g, '');
        
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...updated[updated.length - 1], content: cleanResponse };
          return updated;
        });
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log("War room init cancelled");
      } else {
        setMessages(baseline);
        setProviderError({ message: conversationMessage(err, "War Room initialization failed. Verify the backend runtime and local model, then retry."), lastInput: msgText, requestId, operation: 'init' });
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const handleSend = async (e, textOverride) => {
    if (e && e.preventDefault) e.preventDefault();
    const text = typeof textOverride === 'string' ? textOverride : input;
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', content: text.trim() };

    setProviderError(null);
    const retrying = typeof textOverride === 'string' || (providerError?.operation === 'chat' && providerError.lastInput === userMsg.content);
    const requestId = retrying ? providerError.requestId : crypto.randomUUID();
    const newMessages = retrying ? messages : [...messages, userMsg];
    setMessages(newMessages);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await apiFetch('/api/neural/warroom/chat', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg.content, request_id: requestId }),
        signal: controller.signal,
      });
      if (!res.ok) {
        throw await conversationError(res, "War Room generation failed. Verify Python dependencies, start Ollama, and check the configured model.");
      }
      
      let assistantResponse = "";
      setMessages(prev => [...prev, { role: 'assistant', content: "" }]);
      
      await streamResponse(res, (chunk) => {
        assistantResponse += chunk;
        const cleanResponse = assistantResponse.replace(/<\|im_end\|>/g, '');
        
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...updated[updated.length - 1], content: cleanResponse };
          return updated;
        });
      });
      setInput(current => current.trim() === userMsg.content ? '' : current);
    } catch (err) {
      if (err.name === 'AbortError') {
        setMessages(prev => [...prev, { role: 'assistant', content: "_Transmission cancelled by Keeper._" }]);
      } else {
        setMessages(newMessages);
        setProviderError({ message: conversationMessage(err, "Failed to communicate with War Room. Verify the backend connection and local model, then retry."), lastInput: userMsg.content, requestId, operation: 'chat' });
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const getSpeakerPortrait = (speaker) => {
    const trimmed = (speaker || '').trim();
    const normalized = trimmed.toLowerCase();
    if (normalized.includes('keeper') || normalized.includes('kevin')) {
      return '/assets/keeper.png';
    }
    // Dynamically route companion portraits directly from the Lore Vault via the backend API
    return vaultAssetUrl(`Companions/${trimmed}/Portrait.png`);
  };

  const renderMessage = (msg, idx) => {
    if (msg.role === 'system' || msg.isHidden) {
      return null;
    }

    if (msg.role === 'user') {
      const theme = getSpeakerTheme('Keeper');
      const portrait = getSpeakerPortrait('Keeper');
      return (
        <div key={idx} className={`mb-4 flex justify-end items-start gap-3 w-full`}>
          <div className="flex flex-col items-end max-w-[80%]">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] uppercase tracking-widest font-bold ${theme.textAccent}`}>Keeper</span>
            </div>
            <div className={`p-4 rounded border ${theme.borderAccent} ${theme.bgAccent} ${theme.glow}`}>
              <BanterMarkdown text={msg.content} theme={theme} />
            </div>
          </div>
          <div className="shrink-0 w-20 h-20 rounded-xl border border-white/20 overflow-hidden shadow-lg bg-zinc-800">
            <img 
              src={portrait} 
              alt="Keeper" 
              className="w-full h-full object-cover" 
              onError={(e) => { e.target.style.display = 'none'; }} 
            />
          </div>
        </div>
      );
    } else {
      const lines = msg.content.split('\n');
      const blocks = [];
      let currentBlock = null;

      lines.forEach(line => {
        const trimmed = line.trim();
        if (!trimmed) {
          if (currentBlock) currentBlock.lines.push('');
          return;
        }

        // Match *Name*:, **Name**:, Name:, [Name]:
        const speakerMatch = line.match(/^(?:\*+)?([a-zA-Z0-9_ -]+)(?:\*+)?:\s*(.*)$/) || line.match(/^\[([^\]]+)\]:\s*(.*)$/);
        
        if (speakerMatch) {
          if (currentBlock) blocks.push(currentBlock);
          currentBlock = {
            speaker: speakerMatch[1].trim(),
            lines: [speakerMatch[2]]
          };
        } else {
          if (!currentBlock) {
             currentBlock = {
               speaker: 'System',
               lines: [line]
             };
          } else {
             currentBlock.lines.push(line);
          }
        }
      });
      if (currentBlock) blocks.push(currentBlock);

      return (
        <div key={idx} className="mb-6 flex flex-col items-start gap-3 w-full">
          {blocks.map((block, bIdx) => {
            const { speaker, lines } = block;
            const content = lines.join('\n').trim();
            if (!content) return null;
            
            const theme = getSpeakerTheme(speaker);
            
            if (speaker === 'System') {
               const sysTheme = { textColor: 'text-white/60' };
               return (
                 <div key={`${bIdx}-${speaker}`} className="w-full max-w-[90%] my-1 text-[13px] italic border-l-2 border-white/10 pl-3 py-1">
                   <BanterMarkdown text={content} theme={sysTheme} />
                 </div>
               );
            }

            const portrait = getSpeakerPortrait(speaker);
            return (
              <div key={`${bIdx}-${speaker}`} className="flex items-start gap-3 w-full max-w-[85%] mt-2">
                <div className="shrink-0 w-20 h-20 rounded-xl border border-white/20 overflow-hidden shadow-lg mt-1 bg-zinc-800 flex items-center justify-center">
                  <img 
                    src={portrait} 
                    alt={speaker} 
                    className="w-full h-full object-cover" 
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.style.display = 'none';
                      e.target.parentElement.innerHTML = `<span class="text-xs font-bold text-white/50">${speaker.charAt(0).toUpperCase()}</span>`;
                    }} 
                  />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] uppercase tracking-widest font-bold ${theme.textAccent}`}>{speaker}</span>
                  </div>
                  <div className={`p-4 rounded border ${theme.borderAccent} ${theme.bgAccent} ${theme.glow} whitespace-pre-wrap`}>
                    <BanterMarkdown text={content} theme={theme} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      );
    }
  };

  return (
    <div className="flex flex-col h-full bg-zinc-900/60 rounded border border-white/10 relative overflow-hidden">
      <div className="p-4 border-b border-white/10 shrink-0 flex justify-between items-center">
        <div>
          <h3 className="text-sm font-bold text-accent uppercase tracking-widest">Neural Resonance: War Room</h3>
          <p className="text-[10px] text-white/40 uppercase tracking-widest mt-1 font-mono">Live multi-persona local session</p>
        </div>
        <button onClick={handleClear} className="text-[10px] font-bold text-red-400 uppercase tracking-widest hover:text-red-300">
          Clear Signal
        </button>
      </div>

      {providerError && (
        <div className="p-3 m-4 mb-0 bg-red-950/40 border border-red-500/30 rounded text-red-200 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{providerError.message}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {providerError.operation && (
              <button
                disabled={loading}
                onClick={() => {
                  if (providerError.operation === 'history') loadHistory();
                  else if (providerError.operation === 'init') handleSendSilent(providerError.lastInput, messages, providerError.requestId);
                  else if (providerError.operation === 'clear') handleClear();
                  else handleSend(null, providerError.lastInput);
                }}
                className="px-2.5 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-bold rounded text-[10px] uppercase tracking-wider transition-colors"
              >
                Retry
              </button>
            )}
            <button
              onClick={() => setProviderError(null)}
              className="text-red-400/60 hover:text-red-300 text-xs px-1"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-white/30 text-sm italic font-mono">
            Awaiting transmission...
          </div>
        ) : (
          messages.map(renderMessage)
        )}
        {loading && (
          <div className="flex items-center justify-between bg-zinc-800/80 border border-white/10 rounded px-4 py-2.5 max-w-[80%] mb-4">
            <div className="text-white/50 text-xs font-mono animate-pulse">
              Receiving transmission...
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

      <div className="p-4 border-t border-white/10 bg-black/40 shrink-0">
        <form onSubmit={handleSend} className="flex gap-4">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
            placeholder="Relay command to active squad..."
            className="flex-1 bg-zinc-950 border border-white/10 rounded px-4 py-3 text-sm text-white focus:outline-none focus:border-accent/50 transition-colors placeholder:text-white/20"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-8 bg-accent/10 border border-accent/40 text-accent font-bold uppercase tracking-widest text-xs rounded hover:bg-accent/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Transmit
          </button>
        </form>
      </div>
    </div>
  );
}
