import { motion } from 'framer-motion';
import { useState } from 'react';
import { vaultAssetUrl } from '../lib/desktopApi';

export default function CodexBoard({ entities, onSelectEntity, sectorId }) {
  const cards = entities ? entities.filter(e => e.type === 'directory') : [];

  const forgeTypeMap = {
    'COMPANIONS': { id: 'COMPANION', name: 'Companion' },
    'RESIDENTS': { id: 'RESIDENT', name: 'Resident' },
    'ANTAGONISTS': { id: 'ANTAGONIST', name: 'Antagonist' },
    'BEASTS': { id: 'BEAST', name: 'Beast' },
    'REALMS': { id: 'REALM', name: 'Realm' },
  };

  const forgeInfo = sectorId ? forgeTypeMap[sectorId] : null;


  const getImageUrl = (entityId) => {
    let dirPath = entityId;
    if (dirPath.endsWith('/Profile.md')) dirPath = dirPath.replace('/Profile.md', '');
    if (dirPath.endsWith('/Realm.md')) dirPath = dirPath.replace('/Realm.md', '');
    
    const isRealm = dirPath.startsWith('Realms');
    const filename = isRealm ? 'Landscape.png' : 'Portrait.png';
    const safePath = encodeURIComponent(dirPath).replace(/%2F/g, '/');
    return vaultAssetUrl(`${dirPath}/${filename}`);
  };

  return (
    <div className="h-full w-full bg-zinc-950 p-8 overflow-y-auto custom-scrollbar">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
        {cards.map((card, idx) => (
          <CodexCard 
            key={card.id} 
            entity={card} 
            idx={idx} 
            onSelect={() => onSelectEntity(card)}
            imageUrl={getImageUrl(card.id)}
          />
        ))}
        {cards.length === 0 && !forgeInfo && (
          <div className="col-span-full py-12 text-center text-white/30 font-mono text-sm uppercase tracking-widest border border-dashed border-white/10 rounded-xl">
            No active entities found in this codex.
          </div>
        )}
        {forgeInfo && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: cards.length * 0.05 }}
            onClick={() => onSelectEntity({ id: forgeInfo.id, type: 'virtual', name: `${forgeInfo.name} Blueprint` })}
            className="group relative bg-zinc-900 border border-white/10 hover:border-orange-500/50 rounded-xl cursor-pointer overflow-hidden flex flex-col h-64 transition-all hover:shadow-[0_0_30px_rgba(234,88,12,0.15)]"
          >
            <div className="absolute inset-0 z-0 bg-zinc-900">
               <div className="w-full h-full bg-gradient-to-br from-zinc-800 to-zinc-950 flex items-center justify-center">
                 <span className="text-6xl drop-shadow-md">🛠️</span>
               </div>
            </div>
            <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent z-10" />
            <div className="relative z-20 mt-auto p-4 flex flex-col items-center text-center">
              <h3 className="text-xl font-black text-white group-hover:text-orange-400 transition-colors leading-tight drop-shadow-md">
                Forge {forgeInfo.name}
              </h3>
              <div className="text-[10px] text-white/50 font-mono uppercase tracking-widest mt-2 group-hover:text-orange-400/60 transition-colors">
                Create New ↗
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function CodexCard({ entity, idx, onSelect, imageUrl }) {
  const [imgError, setImgError] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.05 }}
      onClick={onSelect}
      className="group relative bg-zinc-900 border border-white/10 hover:border-accent/50 rounded-xl cursor-pointer overflow-hidden flex flex-col h-64 transition-all hover:shadow-[0_0_30px_rgba(0,212,255,0.15)]"
    >
      {/* Background Image / Fallback */}
      <div className="absolute inset-0 z-0 bg-zinc-900">
        {!imgError ? (
          <img 
            src={imageUrl} 
            alt={entity.name}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-zinc-800 to-zinc-950 flex items-center justify-center">
            <span className="text-6xl opacity-10 drop-shadow-md">👤</span>
          </div>
        )}
      </div>

      {/* Overlay gradient */}
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent z-10" />

      {/* Content */}
      <div className="relative z-20 mt-auto p-4 flex flex-col items-center text-center">
        <h3 className="text-xl font-black text-white group-hover:text-accent transition-colors leading-tight drop-shadow-md">
          {entity.name}
        </h3>
        <div className="text-[10px] text-white/50 font-mono uppercase tracking-widest mt-2 group-hover:text-accent/60 transition-colors">
          View Profile ↗
        </div>
      </div>
    </motion.div>
  );
}
