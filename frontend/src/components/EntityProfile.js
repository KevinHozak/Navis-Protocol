'use client';
import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import CombatProfileModal from './CombatProfileModal';
import { apiFetch, apiUrl } from '../lib/desktopApi';
import VaultAssetImage from './VaultAssetImage';

const MarkdownRenderer = dynamic(() => import('./MarkdownRenderer'), { ssr: false });

export default function EntityProfile({ entityType, entityName, onHopLink, onSelectEntity }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const fetchEntity = async () => {
      setLoading(true);
      try {
        const res = await apiFetch(`/api/entity/${encodeURIComponent(entityType)}/${encodeURIComponent(entityName)}`, {
          signal: controller.signal
        });
        const json = await res.json();
        if (!controller.signal.aborted) {
          setData(json);
        }
      } catch (err) {
        if (!controller.signal.aborted && err?.name !== 'AbortError') {
          console.error(err);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };
    if (entityName) {
      fetchEntity();
    } else {
      setData(null);
      setLoading(false);
    }
    return () => {
      controller.abort();
    };
  }, [entityType, entityName]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div className="bg-red-900/20 border border-red-500/50 text-red-200 p-4 rounded">
        Failed to load entity: {data?.error || 'Unknown error'}
      </div>
    );
  }

  // Determine actions based on type
  const isCombatUnit = ['Companions', 'Antagonists', 'Beasts'].includes(data.type);

  if (data.type === 'Realms') {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Cinematic Realm Banner */}
        <div className="relative w-full h-64 md:h-96 rounded-xl overflow-hidden border border-white/10 shadow-2xl">
          {data.portrait_url ? (
            <VaultAssetImage sourceUrls={[apiUrl(data.portrait_url)]} alt={data.name} className="absolute inset-0 w-full h-full object-cover" fallbackClassName="absolute inset-0 w-full h-full" />
          ) : (
            <div className="absolute inset-0 bg-zinc-900 flex items-center justify-center text-white/20">NO LANDSCAPE DATA</div>
          )}
          {/* Deep Gradient Overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent" />
          
          {/* Realm Title Area */}
          <div className="absolute bottom-0 left-0 w-full p-8">
            <p className="text-accent text-xs font-mono tracking-[0.3em] uppercase mb-2">Tactical Environment</p>
            <h1 className="text-4xl md:text-5xl font-bold text-white tracking-widest uppercase drop-shadow-[0_5px_15px_rgba(0,0,0,0.8)]">
              {data.name}
            </h1>
          </div>
        </div>

        {/* Lore Sections */}
        <div className="grid grid-cols-1 gap-6 mt-8">
          {data.sections.map((section, idx) => (
            <div key={idx} className="bg-zinc-900/60 border border-white/5 rounded-lg p-6 shadow-lg backdrop-blur-sm hover:border-white/10 transition-colors">
              <h2 className="text-sm font-bold text-white/50 uppercase tracking-[0.2em] mb-4 border-b border-white/10 pb-2">
                {section.title}
              </h2>
              <MarkdownRenderer content={section.content} onHopLink={onHopLink} />
            </div>
          ))}

          {/* Sub Documents */}
          {data.sub_documents && data.sub_documents.length > 0 && (
            <div className="bg-zinc-900/60 border border-accent/20 rounded-lg p-6 shadow-lg backdrop-blur-sm transition-colors mt-8">
              <h2 className="text-sm font-bold text-accent uppercase tracking-[0.2em] mb-4 border-b border-white/10 pb-2 flex items-center gap-2">
                <span className="text-lg">📁</span> Local Archives & Planning
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.sub_documents.map((doc, idx) => (
                  <div 
                    key={idx}
                    onClick={() => {
                      if (onSelectEntity) {
                        onSelectEntity({ id: doc.id, type: 'file', name: doc.name });
                      }
                    }}
                    className="p-4 border border-white/10 rounded bg-black/40 hover:bg-white/10 hover:border-accent/50 cursor-pointer transition-all flex items-center gap-3 group shadow-md"
                  >
                    <span className="text-xl opacity-50 group-hover:opacity-100 transition-opacity">📄</span>
                    <div className="flex flex-col truncate">
                      <span className="text-sm font-bold text-white tracking-wide group-hover:text-accent transition-colors truncate">{doc.name}</span>
                      <span className="text-[10px] text-white/40 font-mono mt-1 group-hover:text-white/60 truncate">{doc.path}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header Card (Companions / Antagonists / Beasts) */}
      <div className="bg-zinc-900/80 border border-white/10 rounded-xl overflow-hidden backdrop-blur-md shadow-2xl flex flex-col md:flex-row">
        {/* Avatar/Portrait placeholder */}
        <div className="md:w-1/3 bg-zinc-950 p-6 flex flex-col items-center justify-center border-b md:border-b-0 md:border-r border-white/10">
          <div className="w-56 h-56 rounded-full bg-zinc-800 border-4 border-accent/50 mb-6 shadow-[0_0_20px_rgba(0,212,255,0.3)] overflow-hidden flex items-center justify-center transition-transform hover:scale-105 duration-300">
            {data.portrait_url ? (
              <VaultAssetImage sourceUrls={[apiUrl(data.portrait_url)]} alt={data.name} className="w-full h-full object-cover" fallbackClassName="w-full h-full" />
            ) : (
              <span className="text-6xl">👤</span>
            )}
          </div>
          <h1 className="text-3xl font-bold text-white tracking-wider text-center">{data.name}</h1>
          <p className="text-sm text-accent uppercase tracking-widest mt-2 font-mono">{data.attributes['Class/Title'] || data.type}</p>
        </div>
        
        {/* Quick Stats */}
        <div className={`p-6 flex flex-col justify-center ${data.card_url ? 'md:w-1/3' : 'md:w-2/3'}`}>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(data.attributes).slice(0, 6).map(([key, value]) => (
              <div key={key}>
                <p className="text-[10px] text-white/40 uppercase tracking-widest">{key}</p>
                <p className="text-sm text-white/90 font-medium">{value}</p>
              </div>
            ))}
          </div>
          
          {/* Action Row */}
          <div className="mt-6 flex gap-3">
            {isCombatUnit && (
              <button 
                onClick={() => setIsModalOpen(true)}
                className="px-6 py-2 bg-red-900/50 hover:bg-red-800/60 border border-red-500/30 text-red-400 font-bold uppercase tracking-widest text-xs rounded transition-all shadow-[0_0_10px_rgba(239,68,68,0.2)]"
              >
                ⚔️ View Combat Profile
              </button>
            )}
          </div>
        </div>

        {/* Combat Card Image */}
        {data.card_url && (
          <div className="md:w-1/3 bg-zinc-950/80 p-6 flex flex-col items-center justify-center border-t md:border-t-0 md:border-l border-white/10">
            <div className="w-full max-w-[200px] aspect-[3/4] rounded-lg border-2 border-white/20 shadow-[0_0_30px_rgba(0,0,0,0.5)] overflow-hidden relative group">
              <VaultAssetImage
                sourceUrls={[apiUrl(data.card_url), data.portrait_url && apiUrl(data.portrait_url)]}
                alt="Combat Card"
                className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-500"
                fallbackClassName="w-full h-full"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end p-4">
                 <span className="text-xs text-white font-bold tracking-widest uppercase">TACTICAL ASSET</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Lore Sections */}
      <div className="grid grid-cols-1 gap-6">
        {data.sections.map((section, idx) => (
          <div key={idx} className="bg-zinc-900/60 border border-white/5 rounded-lg p-6 shadow-lg">
            <h2 className="text-sm font-bold text-white/50 uppercase tracking-[0.2em] mb-4 border-b border-white/10 pb-2">
              {section.title}
            </h2>
            <MarkdownRenderer content={section.content} onHopLink={onHopLink} />
          </div>
        ))}

        {/* Sub Documents */}
        {data.sub_documents && data.sub_documents.length > 0 && (
          <div className="bg-zinc-900/60 border border-accent/20 rounded-lg p-6 shadow-lg backdrop-blur-sm transition-colors mt-8">
            <h2 className="text-sm font-bold text-accent uppercase tracking-[0.2em] mb-4 border-b border-white/10 pb-2 flex items-center gap-2">
              <span className="text-lg">📁</span> Local Archives & Planning
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.sub_documents.map((doc, idx) => (
                <div 
                  key={idx}
                  onClick={() => {
                    if (onSelectEntity) {
                      onSelectEntity({ id: doc.id, type: 'file', name: doc.name });
                    }
                  }}
                  className="p-4 border border-white/10 rounded bg-black/40 hover:bg-white/10 hover:border-accent/50 cursor-pointer transition-all flex items-center gap-3 group shadow-md"
                >
                  <span className="text-xl opacity-50 group-hover:opacity-100 transition-opacity">📄</span>
                  <div className="flex flex-col truncate">
                    <span className="text-sm font-bold text-white tracking-wide group-hover:text-accent transition-colors truncate">{doc.name}</span>
                    <span className="text-[10px] text-white/40 font-mono mt-1 group-hover:text-white/60 truncate">{doc.path}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Combat Modal */}
      <CombatProfileModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        entityName={data.name}
        entityType={data.type}
        cardUrl={data.card_url ? apiUrl(data.card_url) : null}
      />
    </div>
  );
}
