"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import dynamic from 'next/dynamic';
import BridgeHome from './BridgeHome';
import NeuralPanel from './NeuralPanel';
import ForgePanel from './ForgePanel';
import BattleCockpit from './BattleCockpit';
import CombatTheater from './CombatTheater';
import ProgressionManifold from './ProgressionManifold';
import ReidInterface from './ReidInterface';
import IronSanctum from '../app/facilities/iron-sanctum/page';
import PrismNexus from '../app/boba-lounge/page';
import LibraryDashboard from '../app/facilities/library/page';
import QuestBoard from './QuestBoard';
import CodexBoard from './CodexBoard';
import CodexBestiaryView from './CodexBestiaryView';
import RecurringBoard from './RecurringBoard';
import TasksBoard from './TasksBoard';
import WarRoom from './WarRoom';
import { apiFetch, apiUrl } from '../lib/desktopApi';
import VaultAssetImage from './VaultAssetImage';
import JournalEntryComposer from './JournalEntryComposer';
import AIExperimentSettings from './AIExperimentSettings';
import WeeklyHolocronView from './WeeklyHolocronView';
import TasksCockpit from './TasksCockpit';

const MarkdownRenderer = dynamic(() => import('./MarkdownRenderer'), { ssr: false });
const EntityProfile = dynamic(() => import('./EntityProfile'), { ssr: false });
const PhaserMapWrapper = dynamic(() => import('./PhaserMapWrapper'), { ssr: false });

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

const parseBanterText = (text, theme) => {
  if (!text) return '';
  const parts = [];
  let currentIndex = 0;
  const regex = /(\*([^\s*][^*]*[^\s*]|[^\s*])\*)|(\[([^\]]+)\])/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    const matchIndex = match.index;
    if (matchIndex > currentIndex) {
      parts.push(
        <span key={`plain-${currentIndex}`} className={theme.textColor}>
          {text.substring(currentIndex, matchIndex)}
        </span>
      );
    }
    if (match[1]) {
      parts.push(
        <span key={`action-${matchIndex}`} className="text-emerald-400/80 italic font-mono text-[13px] mx-1">
          *{match[2]}*
        </span>
      );
    } else if (match[3]) {
      parts.push(
        <span key={`monologue-${matchIndex}`} className="text-purple-400/80 italic font-serif text-[13.5px] mx-1">
          [{match[4]}]
        </span>
      );
    }
    currentIndex = regex.lastIndex;
  }
  if (currentIndex < text.length) {
    parts.push(
      <span key={`plain-${currentIndex}`} className={theme.textColor}>
        {text.substring(currentIndex)}
      </span>
    );
  }
  return parts.length > 0 ? parts : text;
};

export default function SectorView({ 
  sectorId, 
  activeEntity, 
  entityContent, 
  loadingEntities,
  entityLoadError,
  onRetryEntityLoad,
  contentLoadError,
  loadingContent, 
  status,
  entities,
  onSelectEntity,
  onToggleCheckbox,
  onJournalEntrySaved,
  onJournalEntryUnverified,
  journalEntryDraft,
  journalEntryReceipt,
  onRefreshStatus,
  onMissionClick,
  onOpenBestiary,
  onOpenJournal,
  selectedBeast
}) {
  const [banter, setBanter] = useState([]);
  const [banterHistoryError, setBanterHistoryError] = useState(null);
  const [banterError, setBanterError] = useState(null);
  const loadBanterHistory = useCallback(async () => {
    const res = await apiFetch('/api/neural/banter/history');
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || 'Unable to load squad banter history. Retry when the Vault is available.');
    }
    const data = await res.json();
    if (!Array.isArray(data)) throw new Error('Squad banter history returned an invalid response.');
    setBanter(data);
    setBanterHistoryError(null);
  }, []);
  const [generatingBanter, setGeneratingBanter] = useState(false);

  const [activeModel, setActiveModel] = useState("gemini-1.5-flash");
  const [neuralChat, setNeuralChat] = useState([
    { sender: "System", text: "NAVIS Cognitive Manifold initialized. Using gemini-1.5-flash for standard tasks." }
  ]);
  const [chatInput, setChatInput] = useState("");

  const [companions, setCompanions] = useState([]);
  const [realms, setRealms] = useState([]);
  const [realmsLoading, setRealmsLoading] = useState(false);
  const [realmsError, setRealmsError] = useState(null);
  const [realmsLoaded, setRealmsLoaded] = useState(false);
  const [isHopping, setIsHopping] = useState(false);
  const [hopLogs, setHopLogs] = useState(null);
  
  // Phase 2 Draft state
  const [draftRealm, setDraftRealm] = useState(null);
  const [draftData, setDraftData] = useState(null);
  const [selectedDraft, setSelectedDraft] = useState([]);
  const [mapSelectionMessage, setMapSelectionMessage] = useState('');
  const [mapDraftOrigin, setMapDraftOrigin] = useState(false);

  // Combat state
  const [combatLog, setCombatLog] = useState([]);
  const [enemyProfileContent, setEnemyProfileContent] = useState(null);
  
  const [antagonistsList, setAntagonistsList] = useState([]);
  const [beastsList, setBeastsList] = useState([]);

  // Scroll preservation across content updates (e.g. checkbox toggles)
  const scrollContainerRef = useRef(null);
  const scrollPosRef = useRef(0);
  const isSwitchingEntityRef = useRef(false);

  useEffect(() => {
    // When switching active entity, reset scroll position so the new file starts at top
    scrollPosRef.current = 0;
    isSwitchingEntityRef.current = true;
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
    const timer = setTimeout(() => {
      isSwitchingEntityRef.current = false;
    }, 100);
    return () => clearTimeout(timer);
  }, [activeEntity?.id]);

  const handleScroll = (e) => {
    if (!isSwitchingEntityRef.current && e?.currentTarget) {
      scrollPosRef.current = e.currentTarget.scrollTop;
    }
  };

  useEffect(() => {
    // Restore scroll position when entityContent updates for the same active entity
    if (!isSwitchingEntityRef.current && scrollContainerRef.current && scrollPosRef.current > 0) {
      const targetScroll = scrollPosRef.current;
      scrollContainerRef.current.scrollTop = targetScroll;
      requestAnimationFrame(() => {
        if (scrollContainerRef.current && !isSwitchingEntityRef.current) {
          scrollContainerRef.current.scrollTop = targetScroll;
        }
      });
    }
  }, [entityContent]);

  useEffect(() => {
    let interval;
    if (sectorId === 'COMBAT') {
      const fetchLog = async () => {
        try {
          const res = await apiFetch('/api/combat/log');
          const data = await res.json();
          setCombatLog(data.logs || []);
        } catch (err) {
          console.error("Error fetching combat log:", err);
        }
      };
      const fetchEnemies = async () => {
        try {
          const [resAnts, resBeasts] = await Promise.all([
            apiFetch('/api/antagonists'),
            apiFetch('/api/beasts')
          ]);
          setAntagonistsList(await resAnts.json());
          setBeastsList(await resBeasts.json());
        } catch (err) {
          console.error("Error fetching enemy lists:", err);
        }
      };
      fetchLog();
      fetchEnemies();
      interval = setInterval(fetchLog, 15000);
    }
    return () => clearInterval(interval);
  }, [sectorId, activeEntity]);

  useEffect(() => {
    const controller = new AbortController();
    if (activeEntity?.id === 'ANTAGONIST_COMBAT' && status?.current_antagonist) {
      apiFetch(`/api/vault/Obstacles/Antagonists/${encodeURIComponent(status.current_antagonist)}/Profile.md`, { signal: controller.signal })
        .then(res => res.json())
        .then(data => { if (!controller.signal.aborted) setEnemyProfileContent(data.content); })
        .catch(err => { if (!controller.signal.aborted && err?.name !== 'AbortError') setEnemyProfileContent("Failed to load profile."); });
    } else if (activeEntity?.id === 'BEAST_COMBAT' && status?.current_beast) {
      apiFetch(`/api/vault/Obstacles/Beasts/${encodeURIComponent(status.current_beast)}/Profile.md`, { signal: controller.signal })
        .then(res => res.json())
        .then(data => { if (!controller.signal.aborted) setEnemyProfileContent(data.content); })
        .catch(err => { if (!controller.signal.aborted && err?.name !== 'AbortError') setEnemyProfileContent("Failed to load profile."); });
    } else {
      setEnemyProfileContent(null);
    }
    return () => controller.abort();
  }, [activeEntity, status?.current_antagonist, status?.current_beast]);

  const loadRealmOptions = useCallback(async (signal) => {
    setRealmsLoading(true);
    setRealmsError(null);

    try {
      const res = await apiFetch('/api/realm/options', { signal });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || 'Unable to load destination realms.');
      }
      if (!Array.isArray(data)) {
        throw new Error('The destination realm response was invalid.');
      }
      setRealms(data);
      setRealmsLoaded(true);
    } catch (err) {
      if (err?.name === 'AbortError') return;
      setRealms([]);
      setRealmsError(err?.message || 'Unable to load destination realms.');
    } finally {
      if (!signal?.aborted) setRealmsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Companions are shared across sectors, so load them once when the view mounts.
    apiFetch('/api/companions')
      .then(res => res.json())
      .then(data => setCompanions(data || []))
      .catch(err => console.error("Error fetching companions:", err));

  }, []);

  useEffect(() => {
    if (activeEntity?.id !== 'REALM_HOP_MODAL') return undefined;

    const controller = new AbortController();
    loadRealmOptions(controller.signal);
    return () => controller.abort();
  }, [activeEntity?.id, loadRealmOptions]);

  useEffect(() => {
    if (activeEntity?.id === 'BANTER') {
      const fetchBanterHistory = async () => {
        try {
          await loadBanterHistory();
        } catch (err) {
          console.error("Error fetching banter history:", err);
          setBanterHistoryError(err?.message || 'Unable to load squad banter history. Retry when the Vault is available.');
        }
      };
      fetchBanterHistory();
      const interval = setInterval(fetchBanterHistory, 15000);
      return () => clearInterval(interval);
    }
  }, [activeEntity, loadBanterHistory]);

  const handleGenerateBanter = async () => {
    setGeneratingBanter(true);
    setBanterError(null);
    try {
      const res = await apiFetch('/api/neural/banter/generate?count=1', {
        method: "POST"
      });
      if (res.ok) {
        try {
          await loadBanterHistory();
        } catch (err) {
          setBanterHistoryError(err?.message || 'Banter generated, but the feed could not refresh. Retry loading history.');
        }
      } else {
        const data = await res.json().catch(() => ({}));
        setBanterError(data.detail || "Resonance failed. Check the squad and local provider, then retry.");
      }
    } catch (err) {
      console.error("Error generating banter:", err);
      setBanterError(err?.message || "Resonance failed. Check the local provider, then retry.");
    } finally {
      setGeneratingBanter(false);
    }
  };

  const handleDeploy = async (name) => {
    try {
      const payload = { name };
      const targetRecall = activeEntity?.targeting;
      if (targetRecall) {
        payload.target_recall = targetRecall;
      }
      const res = await apiFetch('/api/squad/deploy', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Deploy failed");
      alert(data.message);
      if (onRefreshStatus) {
        await onRefreshStatus();
      } else {
        window.location.reload();
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const handleBench = async (name) => {
    try {
      const res = await apiFetch('/api/squad/bench', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Bench failed");
      alert(data.message);
      if (onRefreshStatus) {
        await onRefreshStatus();
      } else {
        window.location.reload();
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const fetchDraft = async (realmName) => {
    setDraftRealm(realmName);
    setDraftData(null);
    setSelectedDraft([]);
    try {
      const res = await apiFetch(`/api/realm/draft?realm_name=${encodeURIComponent(realmName)}`);
      const data = await res.json();
      if (!res.ok) throw new Error("Failed to fetch draft");
      setDraftData(data);
      return true;
    } catch (e) {
      alert(e.message);
      setDraftRealm(null);
      setMapSelectionMessage(`Unable to load the squad draft for ${realmName}: ${e.message}`);
      return false;
    }
  };

  const handleMapNodeSelect = async (realmName) => {
    setMapSelectionMessage(`Loading squad draft for ${realmName}.`);
    setHopLogs(null);
    setMapDraftOrigin(true);
    onSelectEntity?.({ id: 'REALM_HOP_MODAL', type: 'System', name: 'Moongate Protocol' });
    const loaded = await fetchDraft(realmName);
    if (loaded) setMapSelectionMessage(`Squad draft ready for ${realmName}.`);
  };

  const toggleDraft = (name) => {
    if (selectedDraft.includes(name)) {
      setSelectedDraft(prev => prev.filter(n => n !== name));
    } else {
      if (selectedDraft.length >= 2) return;
      setSelectedDraft(prev => [...prev, name]);
    }
  };

  const handleRealmHop = async () => {
    if (isHopping || !draftRealm || selectedDraft.length !== 2 || !draftData) return;
    setIsHopping(true);
    setHopLogs(null);
    try {
      const activeSquadNames = [draftData.vanguard.name, ...selectedDraft];
      const res = await apiFetch('/api/realm/hop', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ realm_name: draftRealm, squad_names: activeSquadNames })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Realm hop failed");
      setHopLogs(data);
      setDraftRealm(null); // Reset after successful hop
      try {
        await onRefreshStatus?.();
      } catch (refreshError) {
        console.error("Error refreshing status after realm hop:", refreshError);
      }
    } catch (e) {
      setHopLogs({ error: e.message });
    } finally {
      setIsHopping(false);
    }
  };

  const handleNeuralSend = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = { sender: "Keeper", text: chatInput };
    setNeuralChat(prev => [...prev, userMsg]);
    setChatInput("");

    // Simulate AI response with active model complexity rule
    setTimeout(() => {
      const isComplex = chatInput.toLowerCase().includes("analyze") || chatInput.toLowerCase().includes("plan") || chatInput.length > 50;
      const modelUsed = isComplex ? "gemini-1.5-pro" : "gemini-1.5-flash";
      setActiveModel(modelUsed);

      const response = {
        sender: "NAVIS",
        text: `[Cognitive Response via ${modelUsed}]: Understood. Processing instruction: "${chatInput}". Systems remain at optimal capacity.`,
        model: modelUsed
      };
      setNeuralChat(prev => [...prev, response]);
    }, 800);
  };

  // --- Render Virtual Dashboards ---

  // 1. Daily Briefing / Log (STATUS_NEWS)
  const renderNewsBriefing = () => {
    const highlights = status?.recent_activity || [
      "Tactical parameters loaded successfully.",
      "Moongate network synchronization online.",
      "Companion status checked: All systems operational."
    ];
    return (
      <div className="space-y-6">
        <div className="bg-zinc-900/60 p-6 rounded border border-white/10">
          <h3 className="text-sm font-bold text-accent uppercase tracking-widest mb-4">Daily Briefing Log</h3>
          <div className="space-y-4">
            {highlights.map((hl, idx) => (
              <div key={idx} className="flex gap-4 items-start border-l border-white/10 pl-4 py-1">
                <span className="text-[10px] font-mono text-white/30">08:00</span>
                <p className="text-xs text-white/80 font-medium">{hl}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  // 2. Task Checklist (STATUS_TASKS)
  const renderTasksChecklist = () => {
    // Basic tasks extracted from status
    const tasks = status?.tasks || [
      { text: "Perform daily systems audit", status: "/" },
      { text: "Sync companion metrics to cloud run storage", status: "x" },
      { text: "Check moongate calibration parameters", status: " " }
    ];
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-2">Checklist Protocols</h3>
        <div className="space-y-2">
          {tasks.map((task, idx) => (
            <div key={idx} className="p-4 rounded border border-white/5 bg-zinc-900/60 flex items-center justify-between gap-4">
              <span className={`text-xs ${task.status === 'x' ? 'line-through text-white/40' : 'text-white/80'}`}>
                {task.text}
              </span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase ${
                task.status === 'x' ? 'border-green-500/30 text-green-500/80 bg-green-500/5' :
                task.status === '/' ? 'border-accent/30 text-accent bg-accent/5 animate-pulse' :
                'border-white/10 text-white/40 bg-white/5'
              }`}>
                {task.status === 'x' ? 'Completed' : task.status === '/' ? 'In Progress' : 'Pending'}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // 3. Banter Feed (BANTER)
  const renderBanterFeed = () => {
    return (
      <div className="flex flex-col h-[65vh] border border-white/10 rounded bg-zinc-950 overflow-hidden shadow-inner">
        <div className="bg-zinc-900 px-4 py-3 border-b border-white/10 flex justify-between items-center">
          <span className="text-xs font-bold uppercase tracking-wider text-accent flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            Squad Banter Manifold
          </span>
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerateBanter}
              disabled={generatingBanter}
              className={`px-2 py-0.5 rounded text-[9px] font-mono border transition-all ${
                generatingBanter 
                  ? 'border-white/10 text-white/30 bg-zinc-950/50 cursor-not-allowed'
                  : 'border-accent/30 text-accent bg-accent/5 hover:bg-accent/15 active:scale-95'
              }`}
            >
              {generatingBanter ? 'RESONATING...' : '⚡ RESONATE SQUAD'}
            </button>
            <span className="text-[9px] font-mono text-white/30">LOG_LEVEL: BANTER_ACTIVE</span>
          </div>
        </div>
        <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
          {banterHistoryError && (
            <div role="alert" className="rounded border border-amber-400/30 bg-amber-400/5 p-3 text-xs text-amber-200">
              <p>{banterHistoryError}</p>
              <button type="button" onClick={() => loadBanterHistory().catch((err) => setBanterHistoryError(err?.message || 'Unable to load squad banter history.'))} className="mt-2 underline underline-offset-2">Retry loading the feed</button>
            </div>
          )}
          {banterError && (
            <div role="alert" className="rounded border border-red-400/30 bg-red-400/5 p-3 text-xs text-red-200">
              <p>{banterError}</p>
              <button type="button" onClick={handleGenerateBanter} disabled={generatingBanter} className="mt-2 underline underline-offset-2 disabled:opacity-50">Retry resonance</button>
            </div>
          )}
          {!banterHistoryError && banter.length === 0 && (
            <p className="py-8 text-center text-xs text-white/40">
              {Array.isArray(status?.squad) && status.squad.length < 2
                ? 'Deploy at least two squad members before resonating banter.'
                : 'No squad banter history yet. Resonate Squad to create the first thread.'}
            </p>
          )}
          {banter.map((msg, i) => {
            const theme = getSpeakerTheme(msg.sender);
            return (
              <div key={i} className={`flex gap-4 max-w-[85%] ${msg.sender === 'Keeper' ? 'ml-auto flex-row-reverse' : ''}`}>
                <div className={`w-20 h-20 rounded-xl overflow-hidden border-2 bg-zinc-950 shrink-0 ${theme.borderAccent} ${theme.glow}`}>
                  <img 
                    src={msg.avatar ? (msg.avatar.startsWith('http') ? msg.avatar : apiUrl(msg.avatar)) : `https://api.dicebear.com/7.x/identicon/svg?seed=${msg.sender}`}
                    alt={msg.sender}
                    className="w-full h-full object-cover"
                    onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/identicon/svg?seed=${msg.sender}`; }}
                  />
                </div>
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className={`flex items-baseline gap-2 ${msg.sender === 'Keeper' ? 'justify-end' : ''}`}>
                    <span className={`text-xs font-bold uppercase tracking-wider ${theme.textAccent}`}>{msg.sender}</span>
                    <span className="text-[10px] text-white/30 uppercase tracking-widest">{msg.role}</span>
                  </div>
                  <div className={`p-4 rounded-xl text-sm leading-relaxed border ${theme.bgAccent} ${theme.borderAccent} ${theme.glow}`}>
                    {parseBanterText(msg.text, theme)}
                  </div>
                  {msg.realm && (
                    <div className={`text-[10px] opacity-40 italic font-mono ${msg.sender === 'Keeper' ? 'text-right' : ''}`}>
                      Realm: {msg.realm}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // 4. XP Manifold (XP)
  const renderXPManifold = () => {
    return <ProgressionManifold status={status} />;
  };

  // 5. Roster views (ACTIVE_SQUAD, RESERVE_ROSTER)
  const renderRosterView = (type) => {
    const activeList = status?.squad || [];
    const activeNames = activeList.map(c => c.name);
    const targetRecall = activeEntity?.targeting;

    // If RESERVE, show all companions NOT in active squad. Otherwise show ACTIVE
    let list = type === 'ACTIVE'
      ? activeList
      : companions.filter(c => !activeNames.includes(c.name));

    return (
      <div className="space-y-6">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">{type === 'ACTIVE' ? 'Active Squad Roster' : 'Reserve Archive'}</h3>
        {type !== 'ACTIVE' && targetRecall && activeNames.includes(targetRecall) && (
          <div className="text-[11px] font-mono uppercase tracking-widest text-accent bg-accent/10 border border-accent/30 rounded p-3 flex items-center gap-2">
            <span>🎯</span>
            Targeting recall slot: <span className="font-bold text-white">{targetRecall}</span>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {list.map((comp) => (
            <div key={comp.name} className="p-4 bg-zinc-900 border border-white/10 rounded flex flex-col items-center text-center space-y-4 group hover:border-accent/40 transition-all relative">
              <div className="w-20 h-20 rounded-full border border-white/10 overflow-hidden bg-black shadow-lg">
                <VaultAssetImage
                  assetPath={`Companions/${comp.name}/Portrait.png`}
                  fallbackPaths={[`Companions/${comp.name}/Card.png`]}
                  alt={comp.name}
                  className="w-full h-full object-cover"
                  fallbackClassName="w-full h-full"
                />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">{comp.name}</h4>
                <div className="text-[9px] text-accent uppercase font-bold tracking-tight mb-2">{comp.role || 'Companion'}</div>
                <span className="text-[10px] font-mono border border-accent/20 bg-accent/5 px-2 py-0.5 rounded text-accent uppercase font-semibold">
                  LVL {comp.level || 1}
                </span>
              </div>

              <div className="mt-4 w-full">
                {type === 'ACTIVE' ? (
                  <button onClick={() => handleBench(comp.name)} className="w-full py-1.5 border border-red-500/50 text-red-500 text-[10px] font-bold uppercase tracking-widest rounded bg-red-500/5 hover:bg-red-500 hover:text-white transition-colors">
                    Recall
                  </button>
                ) : (
                  <button onClick={() => handleDeploy(comp.name)} className="w-full py-1.5 border border-accent/50 text-accent text-[10px] font-bold uppercase tracking-widest rounded bg-accent/5 hover:bg-accent hover:text-zinc-950 transition-colors">
                    {targetRecall ? `Swap for ${targetRecall}` : 'Deploy'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // 6. Neural Arbiter (NEURAL)
  const renderNeuralInterface = () => {
    return <NeuralPanel persona={activeEntity?.persona} />;
  };

  // 7. Forge blueprints (BLUEPRINTS)
  const renderBlueprints = () => {
    const typeMap = {
      'COMPANION': 'Companion',
      'RESIDENT': 'Resident',
      'ANTAGONIST': 'Antagonist',
      'BEAST': 'Beast',
      'REALM': 'Realm'
    };
    const defaultType = typeMap[activeEntity?.id] || 'Companion';
    return <ForgePanel initialType={defaultType} />;
  };

  // 8. Config Forms (CONFIG)
  const handleTargetChange = async (type, name) => {
    try {
      const res = await apiFetch('/api/combat/target', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, name })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to update target");
      if (onRefreshStatus) {
        await onRefreshStatus();
      }
    } catch (err) {
      console.error("Failed to update target", err);
      alert("Error: " + err.message);
    }
  };


  const renderEnemyMatrix = (type) => {
    const isAntagonist = type === 'Antagonist';
    const list = isAntagonist ? antagonistsList : beastsList;
    const activeName = isAntagonist ? status?.current_antagonist : status?.current_beast;
    const basePath = isAntagonist ? 'Obstacles/Antagonists' : 'Obstacles/Beasts';
    
    return (
      <div className="h-full flex flex-col space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-white/5">
          <h2 className={`text-2xl font-black text-white tracking-widest uppercase italic ${isAntagonist ? 'drop-shadow-[0_0_10px_rgba(255,77,77,0.5)]' : 'drop-shadow-[0_0_10px_rgba(245,158,11,0.5)]'}`}>
            {type} Matrix
          </h2>
          <div className="text-xs font-mono text-white/50">
            Select a target to deploy against.
          </div>
        </div>
        
        {/* Selection Grid */}
        <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 pb-4">
          {list.map(entity => {
            const isActive = activeName === entity.name;
            const borderClass = isActive 
                ? (isAntagonist ? 'border-red-500 shadow-[0_0_15px_rgba(255,77,77,0.4)]' : 'border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]')
                : 'border-white/10 hover:border-white/30 hover:-translate-y-1';
            const textClass = isActive
                ? (isAntagonist ? 'text-red-400' : 'text-amber-400')
                : 'text-white';
            const badgeClass = isAntagonist ? 'bg-red-500' : 'bg-amber-500';

            return (
              <div 
                key={entity.name} 
                onClick={() => handleTargetChange(type.toLowerCase(), entity.name)}
                className={`cursor-pointer rounded-lg overflow-hidden border-2 transition-all group relative bg-black/50 ${borderClass}`}
              >
                <VaultAssetImage
                  assetPath={`${basePath}/${entity.name}/Portrait.png`}
                  fallbackPaths={[`${basePath}/${entity.name}/Card.png`]}
                  className={`w-full h-56 object-cover transition-all ${isActive ? '' : 'opacity-70 group-hover:opacity-100 grayscale group-hover:grayscale-0'}`}
                  fallbackClassName={`w-full h-56 ${isActive ? '' : 'opacity-70'}`}
                />
                <div className={`p-2 text-center bg-zinc-950 ${isActive ? (isAntagonist ? 'border-t-2 border-red-500' : 'border-t-2 border-amber-500') : ''}`}>
                  <div className={`text-[11px] font-bold uppercase tracking-wider mb-0.5 truncate ${textClass}`}>{entity.name}</div>
                  <div className="text-[9px] text-white/40 uppercase font-mono">{entity.role}</div>
                </div>
                {isActive && (
                  <div className={`absolute top-1 right-1 ${badgeClass} text-black text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider`}>
                    Locked
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderBattleField = () => {
    return (
      <div className="h-full flex flex-col space-y-4">
        <CombatTheater status={status} onSelectEntity={onSelectEntity} />
      </div>
    );
  };

  const renderTacticalCockpit = () => {
    return (
      <div className="h-full w-full">
        <BattleCockpit tasks={status?.tasks || []} onTaskResolved={onRefreshStatus} />
      </div>
    );
  };

  const renderConfig = () => {
    return (
      <div className="space-y-6">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">System Settings Config</h3>
        <div className="bg-zinc-900/60 p-6 rounded border border-white/10 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-white/50 uppercase tracking-widest">Interface Mode</label>
              <input type="text" readOnly value="Dark" className="w-full bg-zinc-950 border border-white/10 rounded p-2 text-xs font-mono text-white/60" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-white/50 uppercase tracking-widest">Model Refresher MS</label>
              <input type="text" readOnly value="5000" className="w-full bg-zinc-950 border border-white/10 rounded p-2 text-xs font-mono text-white/60" />
            </div>
          </div>
          <div className="text-right">
            <button className="px-4 py-2 border border-accent text-accent text-xs font-bold uppercase tracking-widest rounded bg-accent/5 hover:bg-accent hover:text-zinc-950 transition-colors">
              Save Parameters
            </button>
          </div>
        </div>
        <AIExperimentSettings />
      </div>
    );
  };

  // 9. Moongate Protocol
  const renderRealmHopModal = () => {
    return (
      <div className="w-full max-w-4xl mx-auto space-y-6">
        <div className="text-center space-y-2 mb-8">
          <div className="text-5xl mb-4">🌀</div>
          <h2 className="text-2xl font-black text-white uppercase tracking-widest">Moongate Protocol</h2>
          <p className="text-[10px] font-mono text-accent uppercase tracking-widest">Current Anchor: {status?.current_realm || 'UNKNOWN'}</p>
        </div>

        <div className="bg-zinc-900/80 border border-white/10 rounded p-6 shadow-2xl relative overflow-hidden">
          {isHopping ? (
            <div className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center z-10 space-y-6">
              <div className="w-16 h-16 border-4 border-accent border-t-transparent rounded-full animate-spin"></div>
              <div role="status" className="text-xs font-bold text-accent uppercase tracking-[0.3em] font-mono animate-pulse">Establishing Resonance...</div>
            </div>
          ) : null}

          <div className="space-y-6 relative z-0">
            {!draftRealm ? (
              // PHASE 1: REALM SELECTION
              <div>
                <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-3 text-center">Stable Resonance Targets</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {realmsLoading && (
                    <div className="col-span-3 text-center py-8 text-accent text-xs font-mono uppercase tracking-widest animate-pulse" role="status">
                      [ CALIBRATING DESTINATION REALMS... ]
                    </div>
                  )}
                  {!realmsLoading && realmsError && (
                    <div className="col-span-3 text-center py-8 space-y-4" role="alert">
                      <p className="text-red-300 text-xs font-mono uppercase tracking-widest">[ REALM SIGNAL LOST ]</p>
                      <p className="text-white/60 text-xs">{realmsError}</p>
                      <button
                        type="button"
                        onClick={() => loadRealmOptions()}
                        className="px-4 py-2 border border-accent text-accent text-[10px] font-bold uppercase tracking-widest rounded hover:bg-accent hover:text-zinc-950 transition-colors"
                      >
                        Retry Resonance Scan
                      </button>
                    </div>
                  )}
                  {!realmsLoading && !realmsError && realms.map(r => (
                    <div key={r.name} className="flex flex-col bg-zinc-950 border border-white/10 rounded overflow-hidden group hover:border-accent transition-all cursor-pointer" onClick={() => fetchDraft(r.name)}>
                      <div className="h-32 bg-black relative">
                        <img 
                          src={`${apiUrl(r.image)}?t=${Date.now()}`}
                          alt={r.name}
                          className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity"
                          onError={(e) => { e.target.style.display = 'none'; }}
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 to-transparent"></div>
                      </div>
                      <div className="p-4 flex-1 flex flex-col">
                        <h3 className="text-sm font-black text-white uppercase tracking-widest mb-2 group-hover:text-accent transition-colors">{r.name}</h3>
                        <p className="text-[10px] text-white/60 font-mono leading-relaxed flex-1 line-clamp-3">
                          {r.description}
                        </p>
                      </div>
                    </div>
                  ))}
                  {!realmsLoading && !realmsError && realmsLoaded && realms.length === 0 && (
                    <div className="col-span-3 text-center py-8 text-white/30 text-xs font-mono uppercase tracking-widest">
                      [ NO STABLE DESTINATION REALMS AVAILABLE ]
                    </div>
                  )}
                </div>
              </div>
            ) : (
              // PHASE 2: SQUAD DRAFT
              <div>
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-sm font-bold text-accent uppercase tracking-widest">Squad Assembly: {draftRealm}</h3>
                  <button onClick={() => {
                    setDraftRealm(null);
                    if (mapDraftOrigin) {
                      setMapDraftOrigin(false);
                      onSelectEntity?.({ id: 'WORLD_MAP', type: 'System', name: 'Overworld Map' });
                    }
                  }} className="text-[10px] uppercase font-bold text-white/50 hover:text-white transition-colors">← Cancel Jump</button>
                </div>
                
                {!draftData ? (
                  <div className="py-12 text-center text-xs font-mono text-accent animate-pulse uppercase tracking-[0.2em]">Calculating Tactical Synergy...</div>
                ) : (
                  <div className="space-y-6">
                    <div className="p-4 border-l-4 border-accent bg-accent/5 rounded-r">
                      <h4 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-2">Slot 1: Vanguard Locked</h4>
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded bg-black border border-accent overflow-hidden shrink-0">
                          <VaultAssetImage
                            assetPath={`Companions/${draftData.vanguard.name}/Portrait.png`}
                            fallbackPaths={[`Companions/${draftData.vanguard.name}/Card.png`]}
                            alt={draftData.vanguard.name}
                            className="w-full h-full object-cover"
                            fallbackClassName="w-full h-full"
                          />
                        </div>
                        <div>
                          <div className="text-sm font-bold text-white uppercase">{draftData.vanguard.name}</div>
                          <div className="text-[10px] text-accent font-mono">Role: {draftData.vanguard.role} | Synergy: +{draftData.vanguard.synergy}</div>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-[10px] font-bold text-white/50 uppercase tracking-widest mb-3 text-center">Draft Pool (Select 2 for Slots 2 & 3)</h4>
                      <div className="space-y-3">
                        {draftData.draft_pool.map(comp => {
                          const isSelected = selectedDraft.includes(comp.name);
                          const isDisabled = !isSelected && selectedDraft.length >= 2;
                          return (
                            <div 
                              key={comp.name} 
                              onClick={() => !isDisabled && toggleDraft(comp.name)}
                              className={`p-3 border rounded flex items-center gap-4 transition-all ${
                                isSelected ? 'bg-accent/10 border-accent' : isDisabled ? 'opacity-40 cursor-not-allowed border-white/5 bg-zinc-950' : 'bg-zinc-950 border-white/10 hover:border-white/30 cursor-pointer'
                              }`}
                            >
                              <div className="w-10 h-10 rounded bg-black border border-white/10 overflow-hidden shrink-0">
                                <VaultAssetImage
                                  assetPath={`Companions/${comp.name}/Portrait.png`}
                                  fallbackPaths={[`Companions/${comp.name}/Card.png`]}
                                  alt={comp.name}
                                  className="w-full h-full object-cover"
                                  fallbackClassName="w-full h-full"
                                />
                              </div>
                              <div className="flex-1">
                                <div className="flex justify-between items-baseline mb-1">
                                  <span className={`text-xs font-bold uppercase ${isSelected ? 'text-accent' : 'text-white'}`}>{comp.name}</span>
                                  <span className="text-[10px] font-mono text-white/60">XP: {comp.xp}</span>
                                </div>
                                <div className="flex justify-between items-baseline">
                                  <span className="text-[9px] text-white/40 uppercase font-mono truncate max-w-[200px]">{comp.tags.join(', ')}</span>
                                  <span className={`text-[10px] font-bold ${comp.synergy > 0 ? 'text-green-400' : 'text-white/30'}`}>Syn: +{comp.synergy}</span>
                                </div>
                              </div>
                              <div className="shrink-0">
                                <div className={`w-4 h-4 rounded border flex items-center justify-center text-[10px] ${isSelected ? 'bg-accent border-accent text-black' : 'border-white/30'}`}>
                                  {isSelected ? '✓' : ''}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className="pt-4 text-center">
                      <button 
                        disabled={selectedDraft.length !== 2}
                        onClick={handleRealmHop}
                        className={`w-full py-3 font-bold uppercase tracking-widest rounded transition-all ${
                          selectedDraft.length === 2 ? 'bg-accent text-black hover:bg-white' : 'bg-zinc-800 text-white/30 cursor-not-allowed'
                        }`}
                      >
                        {selectedDraft.length === 2 ? 'Initiate Anchor Shift' : `Select ${2 - selectedDraft.length} More`}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {hopLogs && (
          <div role={hopLogs.error ? 'alert' : 'status'} className="mt-8 p-4 bg-zinc-950 border border-white/10 rounded shadow-inner">
            <h4 className="text-[10px] font-bold text-accent uppercase tracking-widest mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse" />
              Moongate Telemetry
            </h4>
            <div className="text-[9px] font-mono text-white/60 whitespace-pre-wrap">
              {hopLogs.error ? <span className="text-red-400">Error: {hopLogs.error}</span> : null}
              {hopLogs.stdout && <div className="text-green-400/80 mb-2">{hopLogs.stdout}</div>}
              {hopLogs.stderr && <div className="text-yellow-400/80">{hopLogs.stderr}</div>}
              {hopLogs.message && <div className="text-accent font-bold mt-2">{hopLogs.message}</div>}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Render Dispatcher
  const renderSynthesisLab = () => {
    if (loadingEntities) {
      return (
        <div role="status" className="min-h-[50vh] flex items-center justify-center rounded-lg border border-cyan-400/20 bg-zinc-950/70 p-8">
          <div className="text-center space-y-4">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent" />
            <div className="text-xs font-bold uppercase tracking-[0.3em] text-cyan-300/80">Calibrating synthesis archive...</div>
            <p className="max-w-md text-xs text-white/40">The Lab is contacting the archival manifold. Your forge controls will remain available when synchronization completes.</p>
          </div>
        </div>
      );
    }

    if ((entityLoadError || contentLoadError) && !activeEntity) {
      const errorMessage = entityLoadError?.message || contentLoadError;
      return (
        <div role="alert" className="space-y-6 rounded-lg border border-red-400/30 bg-red-950/20 p-8">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-red-300">Archive request failed</div>
            <h2 className="mt-2 text-2xl font-black uppercase tracking-wider text-white">Synthesis Lab remains online</h2>
            <p className="mt-3 text-sm text-red-100/70">{errorMessage}</p>
          </div>
          {entityLoadError && (
            <button type="button" onClick={onRetryEntityLoad} className="rounded border border-red-300/30 px-4 py-2 text-xs font-bold uppercase tracking-wider text-red-100 hover:bg-red-950/50">
              Retry archive load
            </button>
          )}
          <ForgePanel initialType="Companion" />
        </div>
      );
    }

    if (!activeEntity && entities.length === 0) {
      return (
        <div className="space-y-6 rounded-lg border border-cyan-400/20 bg-zinc-950/70 p-8">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-cyan-300/80">Synthesis Lab // Ready</div>
            <h2 className="mt-2 text-2xl font-black uppercase tracking-wider text-white">No archived entries yet</h2>
            <p className="mt-3 max-w-2xl text-sm text-white/60">The archival shelf is empty, but the Lab is ready. Use the Forge to create the next companion, resident, adversary, beast, or realm.</p>
          </div>
          <ForgePanel initialType="Companion" />
        </div>
      );
    }

    if (!activeEntity) {
      return (
        <div className="min-h-[50vh] flex items-center justify-center rounded-lg border border-cyan-400/20 bg-zinc-950/70 p-8 text-center">
          <div>
            <div className="text-3xl">🧪</div>
            <h2 className="mt-3 text-xl font-black uppercase tracking-wider text-white">Select a Lab entry</h2>
            <p className="mt-2 text-sm text-white/50">Choose an archival entry from the Lab rail to open its dossier.</p>
          </div>
        </div>
      );
    }

    return null;
  };

  const renderViewContent = () => {
    if (sectorId === 'HOLOCRON' || activeEntity?.type === 'holocron') {
      return <WeeklyHolocronView activeWeekId={activeEntity?.week_id} onOpenBestiary={onOpenBestiary} onOpenJournal={onOpenJournal} />;
    }

    if (sectorId === 'DIRECTIVES' || activeEntity?.id === 'TASKS_COCKPIT') {
      return <TasksCockpit onOpenJournal={onOpenJournal} />;
    }

    if (sectorId === 'SYNTHESIS_LAB' && !activeEntity) {
      return renderSynthesisLab();
    }

    if (sectorId === 'KEEPER' && loadingEntities) {
      return (
        <div role="status" className="min-h-[40vh] flex items-center justify-center rounded-lg border border-cyan-400/20 bg-zinc-950/70 p-8 text-center">
          <div>
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-cyan-400 border-t-transparent" />
            <p className="mt-4 text-xs font-bold uppercase tracking-[0.25em] text-cyan-200/80">Loading Keeper records</p>
          </div>
        </div>
      );
    }

    if (sectorId === 'KEEPER' && entityLoadError) {
      const heading = entityLoadError.kind === 'vault-unavailable'
        ? 'Vault unavailable'
        : entityLoadError.kind === 'source-unavailable'
          ? 'Keeper source unavailable'
          : entityLoadError.kind === 'response-invalid'
            ? 'Invalid Keeper response'
            : 'Keeper request failed';
      return (
        <div role="alert" className="rounded-lg border border-red-400/30 bg-red-950/20 p-8">
          <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-red-300">Keeper Ledger</div>
          <h2 className="mt-2 text-xl font-black uppercase tracking-wider text-white">{heading}</h2>
          <p className="mt-3 text-sm text-red-100/70">{entityLoadError.message}</p>
          <button type="button" onClick={onRetryEntityLoad} className="mt-5 rounded border border-red-300/30 px-4 py-2 text-xs font-bold uppercase tracking-wider text-red-100 hover:bg-red-950/50">
            Retry loading records
          </button>
        </div>
      );
    }

    if (sectorId === 'KEEPER' && !activeEntity && entities.length === 0) {
      return (
        <div className="rounded-lg border border-white/10 bg-zinc-950/70 p-8">
          <div className="text-[10px] font-bold uppercase tracking-[0.3em] text-cyan-300/80">Keeper Ledger</div>
          <h2 className="mt-2 text-xl font-black uppercase tracking-wider text-white">No Keeper records found</h2>
          <p className="mt-3 text-sm text-white/60">The Keeper source is available but contains no Markdown records.</p>
          <button type="button" onClick={onRetryEntityLoad} className="mt-5 rounded border border-white/15 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white/80 hover:bg-white/5">
            Check again
          </button>
        </div>
      );
    }

    if (sectorId === 'KEEPER' && !activeEntity) {
      return (
        <div className="min-h-[40vh] flex items-center justify-center rounded-lg border border-cyan-400/20 bg-zinc-950/70 p-8 text-center">
          <div>
            <div className="text-3xl">👑</div>
            <h2 className="mt-3 text-xl font-black uppercase tracking-wider text-white">Select a Keeper record</h2>
            <p className="mt-2 text-sm text-white/50">Choose a record from the Keeper rail to open its dossier.</p>
          </div>
        </div>
      );
    }

    if (loadingContent) {
      return (
        <motion.div
          key="loading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="h-[50vh] flex items-center justify-center"
        >
          <div className="text-center space-y-4">
            <div className="w-12 h-12 border-4 border-accent border-t-transparent rounded-full animate-spin mx-auto" />
            <div className="text-xs uppercase tracking-[0.3em] text-accent/60 font-bold font-mono">Synchronizing core dossier telemetry...</div>
          </div>
        </motion.div>
      );
    }

    if (activeEntity?.type === 'file' || activeEntity?.type === 'directory') {
      const entityPath = activeEntity.path || activeEntity.id || '';
      const pathParts = entityPath.split(/[\\/]/).filter(Boolean);
      
      let isEntityProfile = false;
      let profileType = '';
      let profileName = '';

      if (['Companions', 'Residents', 'Realms'].includes(pathParts[0])) {
        if (pathParts.length === 2) {
          isEntityProfile = true;
          profileType = pathParts[0];
          profileName = pathParts[1];
        } else if (pathParts.length === 3) {
          const fileName = pathParts[2].toLowerCase();
          const isProfileFile = pathParts[0] === 'Realms'
            ? (fileName === 'realm.md' || fileName === 'profile.md')
            : fileName === 'profile.md';
          if (isProfileFile) {
            isEntityProfile = true;
            profileType = pathParts[0];
            profileName = pathParts[1];
          }
        }
      } else if (pathParts.length >= 3 && pathParts[0] === 'Obstacles' && ['Antagonists', 'Beasts'].includes(pathParts[1])) {
        if (pathParts.length === 3) {
          isEntityProfile = true;
          profileType = pathParts[1];
          profileName = pathParts[2];
        } else if (pathParts.length === 4 && pathParts[3].toLowerCase() === 'profile.md') {
          isEntityProfile = true;
          profileType = pathParts[1];
          profileName = pathParts[2];
        }
      }
      
      if (isEntityProfile) {
        return (
          <EntityProfile 
            entityType={profileType} 
            entityName={profileName} 
            onSelectEntity={onSelectEntity}
            onHopLink={(href) => {
              if (href === 'hop://enter_reflection_chamber/') {
                onSelectEntity({ id: 'NEURAL_CHAT', type: 'System', name: 'Neural Bridge', persona: 'Reid' });
              }
            }} 
          />
        );
      }

      if (activeEntity?.type === 'directory' && typeof entityContent === 'object' && entityContent?.type === 'directory_listing') {
        return (
          <div className="w-full max-w-4xl mx-auto space-y-6">
            <h2 className="text-2xl font-bold text-white flex items-center gap-3">
              <span className="text-3xl text-accent">📁</span> {entityContent.name}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {entityContent.items.map(item => (
                <div 
                  key={item.path}
                  onClick={() => onSelectEntity({ id: item.path, type: item.type, name: item.name })}
                  className="p-4 bg-zinc-900 border border-white/10 hover:border-accent/50 hover:bg-zinc-800 rounded flex items-center gap-4 cursor-pointer transition-colors shadow-sm"
                >
                  <span className="text-2xl">{item.type === 'directory' ? '📁' : '📄'}</span>
                  <span className="text-white font-medium truncate">{item.name}</span>
                </div>
              ))}
              {entityContent.items.length === 0 && (
                <div className="col-span-full p-8 text-center text-white/40 italic">
                  This directory is empty.
                </div>
              )}
            </div>
          </div>
        );
      }

      return (
        <div className="w-full max-w-4xl mx-auto bg-zinc-900/40 p-8 border border-white/10 rounded shadow-2xl">
          {sectorId === 'JOURNAL' && (
            <JournalEntryComposer
              key={activeEntity.id}
              date={activeEntity.name?.match(/\d{4}-\d{2}-\d{2}/)?.[0] || ''}
              onSaved={onJournalEntrySaved}
              onUnverified={onJournalEntryUnverified}
              initialDraft={journalEntryDraft}
              savedReceipt={journalEntryReceipt}
            />
          )}
          <MarkdownRenderer 
            key={activeEntity.id}
            content={entityContent} 
            onToggleCheckbox={onToggleCheckbox} 
            onHopLink={(href) => {
              if (href === 'hop://enter_reflection_chamber/') {
                onSelectEntity({ id: 'NEURAL_CHAT', type: 'System', name: 'Neural Bridge', persona: 'Reid' });
              }
            }}
          />
        </div>
      );
    }

    if (activeEntity?.type === 'image') {
      return (
        <div className="flex items-center justify-center p-8 bg-zinc-950 border border-white/10 rounded h-[60vh] relative shadow-inner overflow-hidden">
          <span className="absolute top-2 left-3 text-[9px] font-mono text-white/20 uppercase tracking-widest">Uplink image telemetry</span>
          <img 
            src={`${apiUrl(`/api/vault/${activeEntity.id}`)}?t=${Date.now()}`}
            alt={activeEntity.name} 
            className="max-h-full max-w-full object-contain rounded shadow-2xl border border-white/10" 
          />
        </div>
      );
    }

    // Handle Virtual Dashboards by ID
    switch (activeEntity?.id) {
      case 'STATUS_HUD':
        return <BridgeHome key={activeEntity?._ts || 'hud'} status={status} onMissionClick={onMissionClick} onRefreshStatus={onRefreshStatus} />;
      case 'STATUS_NEWS':
        return renderNewsBriefing();
      case 'STATUS_TASKS':
        return renderTasksChecklist();
      case 'BANTER':
        return renderBanterFeed();
      case 'WAR_ROOM':
        return <WarRoom />;
      case 'XP':
        return renderXPManifold();
      case 'RESERVE_ROSTER':
        return renderRosterView('RESERVE');
      case 'REALM':
      case 'COMPANION':
      case 'RESIDENT':
      case 'ANTAGONIST':
      case 'BEAST':
        return renderBlueprints();

      case 'ANTAGONIST_COMBAT':
        return renderEnemyMatrix('Antagonist');
      case 'BEAST_COMBAT':
        return renderEnemyMatrix('Beast');
      case 'BATTLE':
        return renderBattleField();
      case 'TACTICAL_COCKPIT':
        return renderTacticalCockpit();
      case 'QUEST_BOARD':
        return <QuestBoard entities={entities} onSelectEntity={onSelectEntity} />;
      case 'CODEX_BOARD':
        if (sectorId === 'BEASTS') return <CodexBestiaryView selectedBeast={selectedBeast}><CodexBoard entities={entities} onSelectEntity={onSelectEntity} sectorId={sectorId} /></CodexBestiaryView>;
        return <CodexBoard entities={entities} onSelectEntity={onSelectEntity} sectorId={sectorId} />;
      case 'WORLD_MAP':
        return <div className="flex-1 min-h-[500px] w-full"><PhaserMapWrapper status={status} currentRealm={status?.current_realm || 'Outer Rim'} onSelectRealm={handleMapNodeSelect} />{mapSelectionMessage && <p className="sr-only" role="status">{mapSelectionMessage}</p>}</div>;
      case 'REALM_HOP_MODAL':
        return renderRealmHopModal();
      case 'NEURAL_CHAT':
        return renderNeuralInterface();
      case 'REFLECTION_CHAMBER':
        return <ReidInterface />;
      case 'IRON_SANCTUM':
        return <IronSanctum />;
      case 'PRISM_NEXUS':
        return <PrismNexus />;
      case 'LIBRARY_DASHBOARD':
        return <LibraryDashboard onSelectEntity={onSelectEntity} />;
      case 'CONFIG':
        return renderConfig();
      case 'TASKS_COCKPIT':
        return <TasksCockpit onOpenJournal={onOpenJournal} />;
      default:
        if (activeEntity?.id?.startsWith('RECURRING_BOARD:')) {
          const area = activeEntity.id.split(':')[1];
          return <RecurringBoard area={area} />;
        }
        if (activeEntity?.id?.startsWith('TASKS_BOARD:')) {
          const area = activeEntity.id.split(':')[1];
          return <TasksBoard area={area} />;
        }
        // Fallback for custom file selections or virtual routers
        if (activeEntity?.id?.startsWith('CONFIG:')) {
          return renderConfig();
        }
        return (
          <div className="p-8 bg-zinc-900 border border-white/10 rounded text-center font-mono">
            <span className="text-xs uppercase text-white/30 tracking-widest font-bold">Mounting view data for {activeEntity?.name}...</span>
          </div>
        );
    }
  };

  return (
    <motion.div 
      ref={scrollContainerRef}
      onScroll={handleScroll}
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -10 }}
      className={`h-full flex flex-col ${activeEntity?.id === 'WORLD_MAP' || sectorId === 'DIRECTIVES' || activeEntity?.id === 'TASKS_COCKPIT' ? 'overflow-hidden' : 'overflow-y-auto pr-2'}`}
    >
      {/* Sector Header */}
      {sectorId !== 'HOLOCRON' && activeEntity?.type !== 'holocron' && sectorId !== 'DIRECTIVES' && activeEntity?.id !== 'TASKS_COCKPIT' && (
        <div className="flex items-center gap-4 mb-8 shrink-0">
          <div className="w-12 h-12 rounded border border-accent/30 bg-accent/5 flex items-center justify-center text-2xl">
            {activeEntity?.type === 'file' ? '📄' : activeEntity?.type === 'image' ? '🖼️' : activeEntity?.type === 'directory' ? '📁' : '📦'}
          </div>
          <div>
            <h1 className="text-2xl font-black text-white uppercase tracking-wider">{activeEntity?.name || (sectorId === 'SYNTHESIS_LAB' ? 'SYNTHESIS LAB' : sectorId === 'KEEPER' ? 'KEEPER LEDGER' : 'TACTICAL VIEWPORT')}</h1>
            <div className="text-[10px] text-accent/60 tracking-[0.25em] uppercase font-bold font-mono">
              {activeEntity?.type === 'virtual' ? 'VIRTUAL HUD MANIFOLD' : !activeEntity && sectorId === 'KEEPER' ? `KEEPER RECORDS // ${loadingEntities ? 'LOADING' : entityLoadError ? 'UNAVAILABLE' : entities.length === 0 ? 'EMPTY' : 'SELECT RECORD'}` : `DOSSIER TELEMETRY // ${activeEntity?.id || 'BRIDGE'}`}
            </div>
          </div>
        </div>
      )}

      {/* Render Main Content — keyed per entity so AnimatePresence exits old content instantly */}
      <div className="flex-1 pb-12">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeEntity?.id || 'empty'}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="h-full flex flex-col w-full"
          >
            {renderViewContent()}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
