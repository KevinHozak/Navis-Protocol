"use client";
 
import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch, apiUrl, isTauriRuntime, vaultAssetUrl } from "@/lib/desktopApi";
import NativeCapabilityNotice from "./NativeCapabilityNotice";

export default function ReidInterface() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [loading, setLoading] = useState(true);
  const [providerError, setProviderError] = useState(null);
  const endOfMessagesRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await apiFetch('/api/reid/history');
        const data = await response.json();
        if (data.status === "success" && data.history && data.history.length > 0) {
          setMessages(data.history);
        } else {
          setMessages([
            { role: "reid", content: "Welcome to Friðr Hall, Keeper. How is your mind today?" }
          ]);
        }
      } catch (e) {
        setMessages([
          { role: "reid", content: "Welcome to Friðr Hall, Keeper. How is your mind today?" }
        ]);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsTyping(false);
  };

  const handleSend = async (textOverride) => {
    const text = typeof textOverride === "string" ? textOverride : input;
    if (!text.trim() || isTyping) return;
    const userMsg = text.trim();
    if (typeof textOverride !== "string") setInput("");
    setProviderError(null);
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setIsTyping(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await apiFetch('/api/reid/chat', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, history: messages }),
        signal: controller.signal,
      });
      const data = await response.json();
      
      if (response.ok && data.status === "success") {
        setMessages(prev => [...prev, { role: "reid", content: data.response }]);
        setProviderError(null);
      } else {
        const errorMsg = data.detail || data.message || "Reid conversation service is currently unavailable.";
        setProviderError({ message: errorMsg, lastMsg: userMsg });
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        setMessages(prev => [...prev, { role: "reid", content: "_Transmission cancelled by Keeper._" }]);
      } else {
        setProviderError({ message: e.message || "Connection to Reid interrupted.", lastMsg: userMsg });
      }
    } finally {
      setIsTyping(false);
      abortRef.current = null;
    }
  };
  
  const handleChoiceClick = async (choiceText) => {
    if (isTyping) return;
    setProviderError(null);
    setIsTyping(true);
    setMessages(prev => [...prev, { role: "user", content: choiceText }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await apiFetch('/api/reid/chat', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: choiceText, history: [...messages, { role: "user", content: choiceText }] }),
        signal: controller.signal,
      });
      const data = await response.json();
      if (response.ok && data.status === "success") {
        setMessages(prev => [...prev, { role: "reid", content: data.response }]);
        setProviderError(null);
      } else {
        const errorMsg = data.detail || data.message || "Reid conversation service is currently unavailable.";
        setProviderError({ message: errorMsg, lastMsg: choiceText });
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        setMessages(prev => [...prev, { role: "reid", content: "_Transmission cancelled by Keeper._" }]);
      } else {
        setProviderError({ message: e.message || "Connection to Reid interrupted.", lastMsg: choiceText });
      }
    } finally {
      setIsTyping(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderContent = (content) => {
    if (content.includes("UI_TRIGGER:THREE_DOORS")) {
      return (
        <div className="flex flex-col gap-3 mt-2">
          <p className="text-emerald-300 font-medium">You are overwhelmed. Choose one path forward:</p>
          <motion.button 
            whileHover={{ scale: 1.02 }} 
            onClick={() => handleChoiceClick("I choose Option 1: Step away and reset for 10 minutes.")}
            className="bg-white/5 border border-emerald-500/30 p-3 rounded-lg text-left hover:bg-emerald-500/10 transition-colors"
          >
            1. Step away and reset for 10 minutes.
          </motion.button>
          <motion.button 
            whileHover={{ scale: 1.02 }} 
            onClick={() => handleChoiceClick("I choose Option 2: Delegate the immediate blocker.")}
            className="bg-white/5 border border-emerald-500/30 p-3 rounded-lg text-left hover:bg-emerald-500/10 transition-colors"
          >
            2. Delegate the immediate blocker.
          </motion.button>
          <motion.button 
            whileHover={{ scale: 1.02 }} 
            onClick={() => handleChoiceClick("I choose Option 3: Discard the minor tasks and focus on the core objective.")}
            className="bg-white/5 border border-emerald-500/30 p-3 rounded-lg text-left hover:bg-emerald-500/10 transition-colors"
          >
            3. Discard the minor tasks and focus on the core objective.
          </motion.button>
        </div>
      );
    }
    if (content.includes("UI_TRIGGER:FIVE_MIN_COMMITMENT")) {
      return (
        <div className="p-4 bg-amber-500/10 border border-amber-500/40 rounded-xl text-amber-200">
          <h4 className="font-bold flex items-center gap-2">⏳ 5-Minute Block Initiated</h4>
          <p className="text-sm opacity-80 mt-1">Focus entirely on the task at hand. I will check on you in 5 minutes.</p>
        </div>
      );
    }
    
    // Normal text rendering with Markdown support
    return (
      <div className="text-zinc-300 leading-relaxed whitespace-pre-wrap">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({node, ...props}) => <a {...props} className="text-emerald-400 underline hover:text-emerald-300 transition-colors" target="_blank" rel="noopener noreferrer" />,
            p: ({node, ...props}) => <p {...props} className="mb-2 last:mb-0" />,
            ul: ({node, ...props}) => <ul {...props} className="list-disc pl-5 mb-2" />,
            li: ({node, ...props}) => <li {...props} className="mb-1" />,
            strong: ({node, ...props}) => <strong {...props} className="font-bold text-zinc-100" />
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <div className="relative p-[2px] w-full max-w-3xl mx-auto rounded-3xl bg-gradient-to-br from-zinc-700 via-emerald-800/30 to-amber-700/20 shadow-[0_0_60px_rgba(16,185,129,0.12)]">
      {/* Immersive chamber light overlays */}
      <div className="absolute inset-0 rounded-3xl overflow-hidden pointer-events-none">
        <div className="absolute -top-32 -left-32 w-80 h-80 rounded-full bg-emerald-500/5 blur-[120px]" />
        <div className="absolute -bottom-32 -right-32 w-80 h-80 rounded-full bg-amber-500/5 blur-[120px]" />
      </div>

      <div className="relative flex flex-col h-[600px] w-full rounded-[22px] overflow-hidden bg-zinc-950/90 backdrop-blur-2xl">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-hide">
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} gap-3`}
            >
              {msg.role === "reid" && (
                <div className="w-20 h-20 rounded-xl overflow-hidden shrink-0 border border-emerald-500/20 mt-1">
                  <img 
                    src={vaultAssetUrl('Residents/Reid/Portrait.png')}
                    alt="Reid" 
                    className="w-full h-full object-cover grayscale-[20%]" 
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl p-4 ${
                  msg.role === "user"
                    ? "bg-emerald-600/20 border border-emerald-500/20 text-emerald-100 rounded-br-sm"
                    : "bg-white/5 border border-white/10 text-zinc-300 rounded-bl-sm"
                }`}
              >
                {renderContent(msg.content)}
              </div>
            </motion.div>
          ))}
          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start gap-3"
            >
              <div className="w-20 h-20 rounded-xl overflow-hidden shrink-0 border border-emerald-500/20 mt-1">
                <img 
                  src={vaultAssetUrl('Residents/Reid/Portrait.png')}
                  alt="Reid" 
                  className="w-full h-full object-cover grayscale-[20%]" 
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              </div>
              <div className="bg-white/5 border border-white/10 rounded-2xl rounded-bl-sm p-4 flex gap-1 items-center">
                <span className="w-2 h-2 rounded-full bg-emerald-500/50 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 rounded-full bg-emerald-500/50 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 rounded-full bg-emerald-500/50 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={endOfMessagesRef} />
      </div>

      <div className="p-4 bg-black/40 border-t border-white/5 space-y-3">
        {providerError && (
          <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-red-200 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-base">⚠️</span>
              <span>{providerError.message}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handleSend(providerError.lastMsg)}
                className="px-2.5 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-bold rounded text-[11px] uppercase tracking-wider transition-colors"
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
        <div className="flex items-center gap-3 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Speak to Reid..."
            disabled={isTyping}
            className="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 resize-none"
            rows="1"
          />
          {isTyping ? (
            <button
              onClick={handleCancel}
              className="absolute right-2 px-3 py-1.5 rounded-lg bg-white/10 text-zinc-300 hover:bg-white/20 text-xs font-mono uppercase tracking-wider transition-colors"
            >
              Cancel
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim()}
              className="absolute right-2 p-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  </div>
);
}
