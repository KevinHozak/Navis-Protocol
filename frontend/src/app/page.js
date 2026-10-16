"use client";

import { journalDay } from "@/lib/journalDay";

import { useState, useEffect, useRef } from 'react';
import SovereignRibbon from '@/components/SovereignRibbon';
import SectorRail from '@/components/SectorRail';
import EntityRail from '@/components/EntityRail';
import SecurityGuard from '@/components/SecurityGuard';
import { motion, AnimatePresence } from 'framer-motion';
import SectorView from '@/components/SectorView';
import HorizonRoadmap from '@/components/HorizonRoadmap';
import AsyncJobModal from '@/components/AsyncJobModal';
import AudioEngine from '@/lib/AudioEngine';
import DesktopDiagnostics from '@/components/DesktopDiagnostics';
import { apiFetch, apiUrl, vaultAssetUrl, subscribeVaultStream } from '@/lib/desktopApi';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const API_TIMEOUT_MS = 10000;
const STARTUP_TIMEOUT_MS = 12000;

const FALLBACK_PILLARS = [
  { id: 'COMMAND', label: 'Command Hub', icon: '🛰️', sectors: [{ id: 'STATUS', label: 'Status', icon: '📡' }, { id: 'DIRECTIVES', label: 'Directives', icon: '📋' }] },
  { id: 'SANCTUM', label: 'The Sanctum', icon: '🏰', sectors: [{ id: 'JOURNAL', label: 'Journal', icon: '📓' }] },
  { id: 'CODEX', label: 'Knowledge Base', icon: '📖', sectors: [{ id: 'COMPANIONS', label: 'Companions', icon: '🧙' }] },
];

const HIDDEN_ENTITY_RAIL_SECTORS = [
  'HORIZON_ROADMAP', 'MISSIONS', 'MISSION_MAIN', 'MISSION_SIDE', 'REALM_HOP',
  'RECURRING', 'TASKS', 'WORLD_MAP', 'HOLOCRON', 'DIRECTIVES'
];

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const target = url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url;
    return await apiFetch(target, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

export function getLevelInfo(xp) {
  const currentXp = Math.max(0, xp || 0);
  let level = Math.floor(0.5 + Math.sqrt(0.25 + 2 * currentXp / 1000));
  level = Math.max(1, level);
  const currentLevelBase = 500 * level * (level - 1);
  const nextLevelBase = 500 * (level + 1) * level;
  const progressIntoLevel = currentXp - currentLevelBase;
  const requiredForNext = nextLevelBase - currentLevelBase;
  const percent = Math.min(100, Math.max(0, (progressIntoLevel / requiredForNext) * 100));
  return { level, percent, progressIntoLevel, requiredForNext, currentXp };
}

export default function Home() {
  const [status, setStatus] = useState(null);
  const [pillars, setPillars] = useState([]);
  const [loading, setLoading] = useState(true);
  const [startupMessage, setStartupMessage] = useState(null);
  
  // 4-Fold Navigation State
  const [activePillar, setActivePillar] = useState('COMMAND');
  const [activeSector, setActiveSector] = useState('');
  const [selectedBeast, setSelectedBeast] = useState(null);
  const [entities, setEntities] = useState([]);
  const [activeEntity, setActiveEntity] = useState(null);
  const [loadingEntities, setLoadingEntities] = useState(false);
  const [entityLoadError, setEntityLoadError] = useState(null);
  const [entityRetryVersion, setEntityRetryVersion] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  
  // Content State
  const [entityContent, setEntityContent] = useState('');
  const sourceContentRef = useRef(null);
  const contentRevision = useRef(0);
  const refreshSequence = useRef(0);
  const appliedReadSequence = useRef(0);
  const [pendingCheckboxXP, setPendingCheckboxXP] = useState(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [contentLoadError, setContentLoadError] = useState(null);
  const [loadedContentEntityId, setLoadedContentEntityId] = useState(null);
  const [sectorActiveEntities, setSectorActiveEntities] = useState({});

  const getLocalDateStr = journalDay;

  // Journal Calendar State
  const [selectedJournalDate, setSelectedJournalDate] = useState(getLocalDateStr());

  const refreshStatus = async () => {
    try {
      const res = await fetchWithTimeout(`${API_BASE}/api/status`);
      if (res.ok) {
        const statusData = await res.json();
        setStatus(statusData);
        return statusData;
      }
    } catch (error) {
      console.error("DEBUG: Error refreshing status:", error);
    }
  };

  // Stream & Polling State
  const [streamConnected, setStreamConnected] = useState(false);
  const activeSectorRef = useRef(activeSector);
  activeSectorRef.current = activeSector;
  const selectedJournalDateRef = useRef(selectedJournalDate);
  selectedJournalDateRef.current = selectedJournalDate;
  const activeEntityRef = useRef(activeEntity);
  activeEntityRef.current = activeEntity;

  const refreshActiveEntityContent = async (targetId) => {
    if (checkboxPending.current) return;
    const revision = contentRevision.current;
    const sequence = ++refreshSequence.current;
    try {
      const res = await apiFetch(`/api/vault/${targetId}`, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (res.ok) {
        const data = await res.json();
        if (!checkboxPending.current && revision === contentRevision.current && sequence > appliedReadSequence.current && selectedEntityRef.current === targetId && typeof data.content === 'string') {
          appliedReadSequence.current = sequence;
          sourceContentRef.current = data.source_content ?? data.content;
          setEntityContent(data.content);
          setLoadedContentEntityId(targetId);
          setContentLoadError(null);
          setLoadingContent(false);
        }
      }
    } catch (err) {
      console.warn("DEBUG: Error refreshing active entity content:", err);
    }
  };

  const refreshEntitiesForSector = async (sectorId) => {
    if (!sectorId || sectorId === 'HORIZON_ROADMAP' || sectorId === 'HOLOCRON') return;
    try {
      const res = await apiFetch(`/api/entities?sectorId=${encodeURIComponent(sectorId)}`);
      if (res.ok) {
        const list = await res.json();
        if (Array.isArray(list) && activeSectorRef.current === sectorId) {
          setEntities(list);
        }
      }
    } catch (err) {
      console.warn("DEBUG: Error refreshing entities:", err);
    }
  };

  // 1. Fetch initial status and pillars
  useEffect(() => {
    async function fetchPillars() {
      try {
        const res = await fetchWithTimeout(`${API_BASE}/api/navigation/pillars`);
        if (!res.ok) throw new Error(await res.text());
        const pillarsData = await res.json();
        
        // Remove ARCHIVE sector from CODEX pillar
        const codexPillar = pillarsData.find(p => p.id === 'CODEX');
        if (codexPillar) {
          codexPillar.sectors = codexPillar.sectors.filter(s => s.id !== 'ARCHIVE');
        }
        
        setPillars(pillarsData);
        
        // Default setup for COMMAND pillar
        const commandPillar = pillarsData.find(p => p.id === 'COMMAND');
        if (commandPillar && commandPillar.sectors?.length > 0) {
          const firstSector = commandPillar.sectors[0].id;
          setActiveSector(firstSector);
        }
        return true;
      } catch (error) {
        console.error("DEBUG: Error fetching pillars:", error);
        setPillars(FALLBACK_PILLARS);
        setActiveSector(FALLBACK_PILLARS[0].sectors[0].id);
        return false;
      }
    }

    async function initialFetch() {
      const startupWork = Promise.all([refreshStatus(), fetchPillars()]);
      const deadline = new Promise((resolve) => {
        setTimeout(() => resolve('deadline'), STARTUP_TIMEOUT_MS);
      });
      const result = await Promise.race([
        startupWork.then(() => 'complete'),
        deadline,
      ]);
      if (result === 'deadline') {
        setStartupMessage('Startup synchronization timed out. The cockpit is available, but some Vault data may be delayed.');
      }
      setLoading(false);
    }

    initialFetch();
  }, []);

  // 2. Real-time stream subscription (SSE in web, native listener in desktop)
  useEffect(() => {
    const unsubscribe = subscribeVaultStream({
      onEvent: async (event) => {
        if (!event) return;
        const normEventPath = (event.path || '').replace(/\\/g, '/').toLowerCase();
        const eventType = (event.type || '').toLowerCase();
        const currentEntity = activeEntityRef.current;
        const currentSector = activeSectorRef.current;
        const currentDate = selectedJournalDateRef.current;
        const normActiveEntityPath = (currentEntity?.id || '').replace(/\\/g, '/').toLowerCase();

        // 1. Surgical refresh of active document content (e.g. checkbox edited in Obsidian)
        if (
          currentEntity &&
          (currentEntity.type === 'file' || currentEntity.type === 'directory') &&
          normEventPath &&
          (
            normEventPath === normActiveEntityPath ||
            (currentSector === 'JOURNAL' && currentDate && normEventPath.includes(currentDate))
          )
        ) {
          if (!checkboxPending.current) {
            await refreshActiveEntityContent(currentEntity.id);
          }
        }

        // 2. Status / CompanionStats / Keeper updates
        if (
          eventType === 'bridge' ||
          eventType === 'keeper' ||
          normEventPath.includes('bridge/') ||
          normEventPath.includes('status.json') ||
          normEventPath.includes('companionstats.json') ||
          normEventPath.includes('combat_log') ||
          (eventType === 'journal' && event.action === 'modified')
        ) {
          await refreshStatus();
        }

        // 3. Entity rail updates (if files added/removed in the current sector)
        if (
          event.action === 'created' ||
          event.action === 'deleted' ||
          (currentSector === 'JOURNAL' && eventType === 'journal' && event.action === 'created')
        ) {
          if (currentSector && currentSector !== 'HORIZON_ROADMAP' && currentSector !== 'HOLOCRON') {
            await refreshEntitiesForSector(currentSector);
          }
        }
      },
      onConnectionChange: (connected) => {
        setStreamConnected(connected);
      },
    });

    return () => {
      unsubscribe();
      setStreamConnected(false);
    };
  }, []);

  // 3. Fallback polling retained if stream connection fails or drops; retired when stream is connected
  useEffect(() => {
    if (streamConnected) {
      // Legacy 30s interval retired while active stream is connected
      return;
    }

    // Fallback polling retained if stream connection fails or drops
    const interval = setInterval(refreshStatus, 30000);
    return () => {
      clearInterval(interval);
    };
  }, [streamConnected]);

  // 2. Pillar Change Handler
  const handlePillarSelect = async (pillarId) => {
    if (pillarId === 'SYNC') {
      if (isSyncing) return;
      const confirmMsg = "Initiate Protocol Synchronization?\n\nThis will backup the repository, sync recurring tasks, work logs, bridge status, vitals, and the vault.";
      if (!window.confirm(confirmMsg)) return;

      setIsSyncing(true);
      try {
        const res = await apiFetch('/api/sync?run_async=true', {
          method: 'POST',
        });
        if (!res.ok) {
          throw new Error(await res.text());
        }
        const data = await res.json();
        if (data.status === 'accepted' && data.job_id) {
          setActiveJob({ id: data.job_id, title: "Protocol Synchronization" });
        } else {
          alert("Sync finished but returned an unexpected status.");
        }
      } catch (err) {
        console.error("DEBUG: Sync failed:", err);
        alert(`Sync failed: ${err.message || err}`);
      } finally {
        setIsSyncing(false);
      }
      return;
    }

    setActivePillar(pillarId);
    const pillarObj = pillars.find(p => p.id === pillarId);
    if (pillarObj && pillarObj.sectors?.length > 0) {
      const firstSector = pillarObj.sectors[0].id;
      setActiveSector(firstSector);
    } else {
      setActiveSector('');
      setEntities([]);
      setActiveEntity(null);
    }
  };

  const handleSectorSelect = (sectorId) => {
    if (sectorId === activeSector) {
      if (entities.length > 0) {
        handleEntitySelect(entities[0]);
      }
    } else {
      setActiveSector(sectorId);
    }
  };

  const retryEntityLoad = () => setEntityRetryVersion(version => version + 1);

  // 3. Sector Change: Fetch Entities
  useEffect(() => {
    if (!activeSector) return;
    
    // Immediately clear stale entities so the rail shows skeleton loader
    setEntities([]);
    setActiveEntity(null);
    setEntityLoadError(null);
    setEntityContent('');
    setContentLoadError(null);
    setLoadedContentEntityId(null);
    if (activeSector === 'HORIZON_ROADMAP' || activeSector === 'HOLOCRON') {
      setLoadingEntities(false);
      return;
    }
    setLoadingEntities(true);

    const controller = new AbortController();
    const currentSector = activeSector;
    
    async function fetchEntities() {
      try {
        const res = await apiFetch(`/api/entities?sectorId=${encodeURIComponent(activeSector)}`, {
          signal: controller.signal
        });
        if (!res.ok) {
          const detail = await res.text();
          const error = new Error(detail || `Request failed with status ${res.status}.`);
          error.kind = activeSector === 'KEEPER' && res.status === 404
            ? 'source-unavailable'
            : activeSector === 'KEEPER' && res.status === 503
              ? 'vault-unavailable'
              : 'request-failed';
          throw error;
        }
        const list = await res.json();
        if (!Array.isArray(list) || list.some(entity => !entity || typeof entity.id !== 'string' || typeof entity.name !== 'string' || typeof entity.type !== 'string')) {
          const error = new Error('Entity response did not contain a valid list of records.');
          error.kind = 'response-invalid';
          throw error;
        }

        if (controller.signal.aborted) return;
        setEntities(list);
        
        // Restore last active entity for this sector if any, else match current selected date (if JOURNAL), else use first
        let previous = sectorActiveEntities[currentSector];
        const dashboardSectors = ['REALM_HOP', 'LIBRARY', 'COMPANIONS', 'RESIDENTS', 'ANTAGONISTS', 'BEASTS', 'REALMS', 'DIRECTIVES'];
        if (currentSector.startsWith('MISSION_') || currentSector.startsWith('MISSIONS') || dashboardSectors.includes(currentSector)) {
          previous = null; // Always force dashboards first
        }
        
        let match = previous ? list.find(e => e.id === previous.id) : null;
        
        if (!match && currentSector === 'JOURNAL' && selectedJournalDate) {
          match = list.find(e => e.name === selectedJournalDate || e.id?.includes(selectedJournalDate));
        }
        
        let chosen = null;
        if (match) {
          chosen = match;
        } else if (list.length > 0) {
          chosen = list[0];
        }
        
        setActiveEntity(chosen);
        if (chosen && currentSector === 'JOURNAL') {
          const dateMatch = chosen.name?.match(/\d{4}-\d{2}-\d{2}/) || chosen.id?.match(/\d{4}-\d{2}-\d{2}/);
          if (dateMatch) {
            setSelectedJournalDate(dateMatch[0]);
          }
        }
      } catch (error) {
        if (controller.signal.aborted || error?.name === 'AbortError') return;
        console.error("DEBUG: Error fetching entities:", error);
        const errorMessage = error.message || String(error);
        const nativeVaultUnavailable = currentSector === 'KEEPER' && /Vault root is unavailable/i.test(errorMessage);
        const nativeSourceUnavailable = currentSector === 'KEEPER' && /Keeper source directory is unavailable/i.test(errorMessage);
        setEntityLoadError({
          kind: error.kind || (nativeVaultUnavailable ? 'vault-unavailable' : nativeSourceUnavailable ? 'source-unavailable' : error instanceof SyntaxError ? 'response-invalid' : 'request-failed'),
          message: `Unable to load ${currentSector || 'this view'}: ${errorMessage}`,
        });
      } finally {
        if (!controller.signal.aborted) {
          setLoadingEntities(false);
        }
      }
    }
    fetchEntities();

    return () => {
      controller.abort();
    };
  }, [activeSector, entityRetryVersion]);

  // 4. Entity Change: Fetch File Content if type is file/directory
  useEffect(() => {
    contentRevision.current += 1;
    if (!activeEntity) {
      setEntityContent('');
      setLoadedContentEntityId(null);
      setLoadingContent(false);
      return;
    }
    
    if (activeEntity.type === 'file' || activeEntity.type === 'directory') {
      // Clear stale content immediately so loading spinner shows at once
      setEntityContent('');
      setLoadedContentEntityId(null);
      setLoadingContent(true);

      const controller = new AbortController();
      const targetEntityId = activeEntity.id;
      const revision = contentRevision.current;
      const sequence = ++refreshSequence.current;
      
      apiFetch(`/api/vault/${targetEntityId}`, { signal: controller.signal, cache: 'no-store' })
        .then(async res => {
          if (!res.ok) throw new Error(await res.text());
          return res.json();
        })
        .then(data => {
          if (controller.signal.aborted || revision !== contentRevision.current || sequence <= appliedReadSequence.current) return;
          appliedReadSequence.current = sequence;
          setEntityContent(data.content || '');
          sourceContentRef.current = data.source_content ?? data.content;
          setLoadedContentEntityId(targetEntityId);
          setContentLoadError(null);
          setLoadingContent(false);
        })
        .catch(err => {
          if (controller.signal.aborted || revision !== contentRevision.current || sequence <= appliedReadSequence.current || err?.name === 'AbortError') return;
          console.error("DEBUG: Error fetching file content:", err);
          const message = err?.message || String(err);
          setContentLoadError(`Unable to load ${activeEntity.name || 'selected file'}: ${message}`);
          setEntityContent(`### Error Loading File\nUnable to retrieve telemetry: ${message}`);
          setLoadedContentEntityId(null);
          setLoadingContent(false);
        });

      return () => {
        controller.abort();
      };
    } else {
      setEntityContent('');
      setLoadedContentEntityId(null);
      setLoadingContent(false);
    }
  }, [activeEntity]);

  const handleEntitySelect = (entity) => {
    setActiveEntity({ ...entity, _ts: Date.now() });
    setSectorActiveEntities(prev => ({
      ...prev,
      [activeSector]: entity
    }));
    // Keep journal calendar in sync when user clicks entity directly
    if (activeSector === 'JOURNAL') {
      const dateMatch = entity.name?.match(/\d{4}-\d{2}-\d{2}/) || entity.id?.match(/\d{4}-\d{2}-\d{2}/);
      if (dateMatch) setSelectedJournalDate(dateMatch[0]);
    }
  };

  const checkboxPending = useRef(false);
  const selectedEntityRef = useRef(activeEntity?.id);
  selectedEntityRef.current = activeEntity?.id;
  const handleToggleCheckbox = async (targetText, isChecked, lineNumber, expectedContent = sourceContentRef.current) => {
    console.log("DEBUG: handleToggleCheckbox called with:", { targetText, isChecked, lineNumber });
    if (!activeEntity || (activeEntity.type !== 'file' && activeEntity.type !== 'directory')) {
      console.log("DEBUG: No valid file activeEntity is selected.");
      return { ok: false };
    }

    // Keep selected journal date, file path and displayed checkbox content aligned before allowing mutations
    if (loadingContent || loadedContentEntityId !== activeEntity.id) {
      console.warn("DEBUG: Checkbox mutation rejected: loaded content is not aligned with active entity path.");
      return { ok: false };
    }

    if (activeSector === 'JOURNAL') {
      const entityDate = activeEntity.name?.match(/\d{4}-\d{2}-\d{2}/)?.[0] || activeEntity.id?.match(/\d{4}-\d{2}-\d{2}/)?.[0];
      if (!entityDate || entityDate !== selectedJournalDate) {
        console.warn("DEBUG: Checkbox mutation rejected: selected journal date is not aligned with active entity.");
        return { ok: false };
      }
    }

    if (checkboxPending.current) return { ok: false, busy: true };
    checkboxPending.current = true;
    const revision = ++contentRevision.current;
    const entityId = activeEntity.id;
    try {
      const res = await apiFetch('/api/tasks/toggle', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(20000),
        body: JSON.stringify({ file_path: entityId, target_text: targetText,
          is_checked: isChecked, line_number: lineNumber, expected_content: expectedContent })
      });
      const result = await res.json();
      const authoritative = res.ok ? result : result.detail;
      if (revision === contentRevision.current && selectedEntityRef.current === entityId && typeof authoritative?.content === 'string') {
        sourceContentRef.current = authoritative.source_content ?? authoritative.content;
        setEntityContent(authoritative.content);
      }
      if (!res.ok) throw new Error(authoritative?.message || result.detail || 'Task update failed');
      if (result.xp_status === 'pending') {
        setPendingCheckboxXP({ entityId, targetText, isChecked, lineNumber, expectedContent: result.source_content ?? result.content });
      } else { setPendingCheckboxXP(null); }
      refreshStatus().catch(err => console.warn('Status refresh failed after task save', err));
      return { ok: true, result };
    } catch (err) {
      // Lost responses can follow successful saves. Read back instead of reverting.
      try {
        const res = await apiFetch(`/api/vault/${entityId}`, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
        const result = await res.json();
        if (res.ok && revision === contentRevision.current && selectedEntityRef.current === entityId && typeof result.content === 'string') {
          sourceContentRef.current = result.source_content ?? result.content;
          setEntityContent(result.content);
        }
      } catch (reloadError) { console.warn('Task read-back unavailable', reloadError); }
      alert(`Task update needs review: ${err.message || err}`);
      return { ok: false, error: err };
    } finally {
      contentRevision.current += 1;
      checkboxPending.current = false;
      // Replay watcher reads suppressed during persistence, including navigation away/back.
      if (selectedEntityRef.current) await refreshActiveEntityContent(selectedEntityRef.current);
    }
  };

  // Journal Calendar: when a date is picked, find the matching entity in the rail
  const handleJournalDateSelect = (dateStr) => {
    setSelectedJournalDate(dateStr);
    // Entities in JOURNAL sector are named by date (e.g. "2026-05-20")
    const match = entities.find(e => e.name === dateStr || e.id?.includes(dateStr));
    if (match) {
      handleEntitySelect(match);
    } else {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const [yyyy, mm] = parts;
        handleEntitySelect({
          id: `Journal/${yyyy}/${mm}/${dateStr}.md`,
          name: dateStr,
          type: 'file',
        });
      }
    }
  };

  const handleJournalEntrySaved = (result) => {
    if (result?.content) {
      contentRevision.current += 1;
      sourceContentRef.current = result.content;
      setEntityContent(result.content);
      if (activeEntity?.id) {
        setLoadedContentEntityId(activeEntity.id);
      }
    }
    if (result?.date) setSelectedJournalDate(result.date);
  };

  const handleRolloverComplete = async (newDate) => {
    try {
      // 1. Fetch updated status (XP/squad/metadata changes)
      const statusRes = await apiFetch('/api/status');
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStatus(statusData);
      }
      
      // 2. Fetch updated journal files list
      const res = await apiFetch('/api/entities?sectorId=JOURNAL');
      if (res.ok) {
        const list = await res.json();
        setEntities(list);
        
        // 3. Select the new rollover date
        setSelectedJournalDate(newDate);
        const match = list.find(e => e.name === newDate || e.id?.includes(newDate));
        if (match) {
          handleEntitySelect(match);
        }
      }
    } catch (error) {
      console.error("DEBUG: Error processing rollover completion:", error);
    }
  };

  const handleMissionClick = (missionName, mission) => {
    if (!mission || !mission.path) return;
    const rawPath = mission.path.replace(/\\/g, '/');
    const relPath = rawPath.split('Navis-Vault/')[1];
    if (!relPath) {
      console.error('Could not derive vault path for mission:', missionName, mission.path);
      return;
    }
    handleEntitySelect({
      id: relPath,
      name: missionName,
      type: 'file',
      mission_type: mission.mission_type || 'Main'
    });
  };

  const [realmTexture, setRealmTexture] = useState('url(\'/bg_texture.png\')');

  useEffect(() => {
    if (status?.current_realm && status.current_realm !== 'Unknown') {
      const textureUrl = vaultAssetUrl(`Realms/${status.current_realm}/Texture.png`);
      const img = new Image();
      img.onload = () => setRealmTexture(`url('${textureUrl}')`);
      img.onerror = () => setRealmTexture('url(\'/bg_texture.png\')');
      img.src = textureUrl;
    } else {
      setRealmTexture('url(\'/bg_texture.png\')');
    }
  }, [status?.current_realm]);

  if (loading) {
    return (
      <div
        className="h-screen w-screen bg-[#050505] flex items-center justify-center font-mono"
        style={{ backgroundColor: '#050505', color: '#5dade2', minHeight: '100vh' }}
      >
        <div className="text-center space-y-4" style={{ color: '#5dade2' }}>
          <svg
            aria-label="Synchronizing"
            role="img"
            viewBox="0 0 64 64"
            width="64"
            height="64"
            style={{ display: 'block', margin: '0 auto', overflow: 'visible' }}
          >
            <circle cx="32" cy="32" r="26" fill="none" stroke="#17364a" strokeWidth="4" />
            <circle cx="32" cy="32" r="26" fill="none" stroke="#5dade2" strokeWidth="4" strokeLinecap="round" strokeDasharray="40 124">
              <animateTransform attributeName="transform" type="rotate" from="0 32 32" to="360 32 32" dur="1s" repeatCount="indefinite" />
            </circle>
          </svg>
          <div className="text-xs uppercase tracking-[0.4em] text-accent font-bold" style={{ color: '#5dade2' }}>Synchronizing Sovereign Uplink...</div>
        </div>
      </div>
    );
  }

  // Find sectors for active pillar
  const currentPillarObj = pillars.find(p => p.id === activePillar);
  const currentSectors = activePillar === 'COMMAND'
    ? [...(currentPillarObj?.sectors || []).filter(sector => sector.id !== 'HORIZON_ROADMAP'), { id: 'HORIZON_ROADMAP', label: 'Horizon Roadmap', icon: '🗺️' }]
    : currentPillarObj?.sectors || [];
  const isCodexRosterSector = ['COMPANIONS', 'RESIDENTS', 'ANTAGONISTS', 'BEASTS', 'REALMS'].includes(activeSector);

  return (
    <SecurityGuard>
      <main 
        className="flex flex-col h-screen overflow-hidden realm-bg bg-zinc-950"
        style={{ '--realm-bg-url': realmTexture }}
      >
        {pendingCheckboxXP?.entityId === activeEntity?.id && (
          <div role="status" className="fixed bottom-4 right-4 z-50 rounded border border-amber-400/40 bg-zinc-950/90 p-3 text-sm text-amber-200 backdrop-blur-md">
            Task saved. XP pending.
            <button className="ml-3 underline" onClick={() => handleToggleCheckbox(pendingCheckboxXP.targetText, pendingCheckboxXP.isChecked, pendingCheckboxXP.lineNumber, pendingCheckboxXP.expectedContent)}>Retry XP</button>
          </div>
        )}
        {startupMessage && (
          <div role="alert" className="fixed top-3 left-1/2 z-50 w-[min(90vw,44rem)] -translate-x-1/2 rounded border border-amber-400/40 bg-amber-950/90 px-4 py-3 text-center font-mono text-[10px] uppercase tracking-wider text-amber-200 shadow-xl backdrop-blur-md">
            {startupMessage}
          </div>
        )}
        {(contentLoadError || (entityLoadError && activeSector !== 'KEEPER')) && (
          <div role="alert" className="fixed top-3 right-3 z-50 max-w-[min(90vw,32rem)] rounded border border-red-400/40 bg-red-950/90 px-4 py-3 font-mono text-[10px] uppercase tracking-wider text-red-200 shadow-xl backdrop-blur-md">
            {contentLoadError || entityLoadError.message}
          </div>
        )}
        {/* Level 1: Sovereign Ribbon */}
        <SovereignRibbon 
          realm={status?.current_realm}
          navItems={pillars}
          activeId={activePillar} 
          onSelect={handlePillarSelect}
          isSyncing={isSyncing}
        />

        <div className={`flex flex-1 ${isCodexRosterSector ? 'flex-col md:flex-row' : 'flex-row'} overflow-hidden relative`}>
          {/* Level 2 & 3: Sector Rail + Entity Rail */}
          {activePillar !== 'LIBRARY' && activePillar !== 'IRON' && activePillar !== 'PRISM' && (
            <div className={`flex shrink-0 ${isCodexRosterSector ? 'flex-col md:flex-row' : ''}`}>
              <SectorRail 
                sectors={currentSectors} 
                activeSector={activeSector} 
                onSelect={handleSectorSelect} 
                compact={isCodexRosterSector}
              />
              {!HIDDEN_ENTITY_RAIL_SECTORS.some(prefix => activeSector?.startsWith(prefix)) && (
                <EntityRail 
                  entities={entities} 
                  activeEntityId={activeEntity?.id} 
                  onSelect={handleEntitySelect} 
                  activeSector={activeSector}
                  loading={loadingEntities}
                  entityLoadError={activeSector === 'KEEPER' ? entityLoadError : null}
                  onRetry={retryEntityLoad}
                  selectedJournalDate={selectedJournalDate}
                  onJournalDateSelect={handleJournalDateSelect}
                  onRolloverComplete={handleRolloverComplete}
                />
              )}
            </div>
          )}

          {/* Level 4: Central Tactical Viewport */}
          <div className={`min-h-0 min-w-0 flex-1 overflow-hidden relative ${activeSector === 'HORIZON_ROADMAP' ? '' : 'p-3 md:p-8'} bg-zinc-950/95 border-r border-white/5 shadow-2xl flex flex-col`}>
            {activeSector === 'HORIZON_ROADMAP' ? <HorizonRoadmap /> : (
            <AnimatePresence mode="wait">
              <SectorView 
                key={`${activeSector}-${activeEntity?.id}`}
                sectorId={activeSector} 
                activeEntity={activeEntity}
                entities={entities}
                loadingEntities={loadingEntities}
                entityLoadError={entityLoadError}
                onRetryEntityLoad={retryEntityLoad}
                entityContent={entityContent}
                contentLoadError={contentLoadError}
                loadingContent={loadingContent}
                status={status}
                onSelectEntity={handleEntitySelect}
                onToggleCheckbox={handleToggleCheckbox}
                onJournalEntrySaved={handleJournalEntrySaved}
                onRefreshStatus={refreshStatus}
                onMissionClick={handleMissionClick}
                selectedBeast={selectedBeast}
                onOpenBestiary={(name) => {
                  const codex = pillars.find(p => p.sectors?.some(s => s.id === 'BEASTS'));
                  if (codex) setActivePillar(codex.id);
                  setSelectedBeast(name);
                  setActiveEntity({ id: 'CODEX_BOARD', type: 'virtual', name: 'Beasts Codex' });
                  setActiveSector('BEASTS');
                }}
              />
            </AnimatePresence>
            )}
          </div>

          {/* Right Side: Integrated Dossier + Party Rail */}
          {activeSector !== 'HORIZON_ROADMAP' && activePillar !== 'PRISM' && (
            <aside className="hidden xl:flex w-[320px] border-l border-white/5 bg-black/30 flex-col z-30 shadow-2xl shrink-0">
              {/* Header: Realm Info */}
              <div className="p-6 border-b border-white/5 relative overflow-hidden group">
              <div className="absolute inset-0 bg-accent/5 group-hover:bg-accent/10 transition-colors pointer-events-none" />
              <div className="relative z-10">
                <div className="text-[9px] uppercase tracking-[0.4em] text-accent/60 mb-2 font-bold flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  Active Realm
                </div>
                <div className="text-xl font-black text-white tracking-tight drop-shadow-lg uppercase italic">{status?.current_realm || 'Unknown'}</div>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <div className="p-4 space-y-6">
                {/* Realm Image */}
                {status?.current_realm && (
                  <div className="w-full h-36 rounded overflow-hidden border border-white/10 bg-zinc-900/20 shadow-lg relative group">
                    <img 
                      src={vaultAssetUrl(`Realms/${status.current_realm}/Landscape.png`)}
                      alt={status.current_realm}
                      className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                      onError={(e) => { e.target.src = '/bg_texture.png'; }}
                    />
                  </div>
                )}

                {/* Squad Section */}
                <div className="space-y-3">
                  <h3 className="text-[9px] font-bold uppercase tracking-[0.3em] text-white/30 border-b border-white/5 pb-2">
                    Active Squad
                  </h3>
                  <div className="grid grid-cols-1 gap-2.5">
                    {/* The Keeper (Fixed at Top) */}
                    {(() => {
                      const keeperXP = status?.keeper_xp ?? status?.keeper_entry_xp ?? 0;
                      const kInfo = getLevelInfo(keeperXP);
                      return (
                        <div className="p-3 rounded border border-accent/40 bg-zinc-950/80 shadow-[0_0_15px_rgba(0,212,255,0.03)] group flex gap-3 items-center relative overflow-hidden">
                          <div className="absolute top-0 right-0 p-1 opacity-10">
                            <span className="text-3xl">👑</span>
                          </div>
                          <div className="w-12 h-12 shrink-0 rounded overflow-hidden border border-accent/40 bg-black shadow-lg">
                            <img 
                              src="/assets/keeper.png" 
                              alt="Keeper"
                              className="w-full h-full object-cover transition-all duration-700"
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex justify-between items-start mb-0.5">
                              <span className="text-xs font-bold text-accent uppercase tracking-[0.2em]">KEEPER</span>
                              <span className="text-[9px] font-mono text-accent">LVL {status?.keeper_level || kInfo.level}</span>
                            </div>
                            <div className="flex justify-between items-center mb-1.5">
                              <div className="text-[9px] text-white/50 uppercase italic tracking-wider">Primary Authority</div>
                              <div className="text-[9px] text-white/30 font-mono">{kInfo.currentXp} XP</div>
                            </div>
                            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden" title={`${kInfo.currentXp} XP`}>
                              <div className="h-full bg-accent shadow-[0_0_8px_rgba(0,212,255,0.5)]" style={{ width: `${kInfo.percent}%` }} />
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Other Companions */}
                    {status?.squad?.map((entity) => {
                      const entityXP = entity.xp ?? entity.entry_xp ?? 0;
                      const eInfo = getLevelInfo(entityXP);
                      return (
                      <div key={entity.name} className="p-3 rounded border border-white/5 hover:border-accent/20 bg-zinc-950/80 transition-all group flex gap-3 items-center relative overflow-hidden">
                        <div className="w-12 h-12 shrink-0 rounded overflow-hidden border border-white/10 group-hover:border-accent/40 transition-all">
                          <img 
                            src={vaultAssetUrl(`Companions/${entity.name}/Portrait.png`)}
                            alt={entity.name}
                            className="w-full h-full object-cover transition-all duration-500"
                            onError={(e) => {
                              const fallbackUrl = `/assets/companions/${entity.name.toLowerCase().replace("'", "").replace(" ", "_")}.png`;
                              if (e.target.src !== fallbackUrl && !e.target.src.endsWith(fallbackUrl)) {
                                e.target.src = fallbackUrl;
                              } else {
                                e.target.src = `https://api.dicebear.com/7.x/identicon/svg?seed=${entity.name}`;
                              }
                            }}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex justify-between items-start mb-0.5">
                            <span className="text-xs font-bold text-white/80 uppercase tracking-widest truncate group-hover:text-accent transition-colors">{entity.name}</span>
                            <span className="text-[9px] font-mono text-white/40">LVL {entity.level || eInfo.level}</span>
                          </div>
                          <div className="flex justify-between items-center mb-1.5">
                            <div className="text-[9px] text-accent/60 uppercase font-bold tracking-tighter italic">
                              {entity.role || 'Companion'}
                            </div>
                            <div className="text-[9px] text-white/30 font-mono">{eInfo.currentXp} XP</div>
                          </div>
                          <div className="space-y-1">
                            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden" title={`${eInfo.currentXp} XP`}>
                              <motion.div 
                                initial={{ width: 0 }}
                                animate={{ width: `${eInfo.percent}%` }}
                                className="h-full bg-accent/60"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                      );
                    })}
                  </div>
                </div>

                {/* Console Section */}
                <div className="space-y-3">
                  <h3 className="text-[9px] font-bold uppercase tracking-[0.3em] text-white/30 border-b border-white/5 pb-2">
                    Terminal Pulse
                  </h3>
                  <div className="bg-zinc-950 p-4 font-mono text-[9px] space-y-1.5 text-accent/80 leading-relaxed border border-white/5 h-36 overflow-hidden relative shadow-inner rounded">
                    <div className="text-green-500/60">&gt; NAVIS_INIT_SUCCESS</div>
                    <div className="text-white/20">&gt; SCROLL_LOCK_ACTIVE</div>
                    <div className="text-accent/60">&gt; {status?.current_realm?.toUpperCase()}_CONNECTED</div>
                    <div className="text-white/10 italic">&gt; Awaiting Keeper input...</div>
                    <div className="text-accent animate-pulse">&gt; _</div>
                    <div className="absolute inset-0 pointer-events-none bg-gradient-to-t from-zinc-950 to-transparent" />
                  </div>
                </div>
              </div>
            </div>
          </aside>
        )}
        </div>
      </main>
      <DesktopDiagnostics />
      {activeJob && (
        <AsyncJobModal 
          jobId={activeJob.id} 
          title={activeJob.title} 
          onClose={() => setActiveJob(null)}
          onComplete={() => {
            refreshStatus();
          }}
        />
      )}
    </SecurityGuard>
  );
}
