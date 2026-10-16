import { motion } from 'framer-motion';
import { apiUrl } from '../lib/desktopApi';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function QuestBoard({ entities, onSelectEntity }) {
  // Filter out the virtual QUEST_BOARD entity
  const missions = entities ? entities.filter(e => e.type === 'file') : [];

  return (
    <div className="h-full w-full bg-zinc-950 p-8 overflow-y-auto">
      <div className="mb-8 border-b border-white/10 pb-4">
        <h1 className="text-4xl font-black uppercase tracking-tight text-white flex items-center gap-4">
          <span className="text-amber-500">🚩</span> Active Quests
        </h1>
        <p className="text-white/40 font-mono text-sm uppercase tracking-widest mt-2">
          Select a mission to view telemetry
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {missions.map((mission, idx) => {
          const basePath = mission.id ? mission.id.substring(0, mission.id.lastIndexOf('/')) : '';
          const encodedPath = basePath.split('/').map(encodeURIComponent).join('/');
          const imageUrl = `${apiUrl(`/api/vault/${encodedPath}/Landscape.png`)}`;

          return (
            <motion.div
              key={mission.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              onClick={() => onSelectEntity(mission)}
              className={`group relative bg-zinc-900/50 border border-white/10 rounded-xl p-6 cursor-pointer overflow-hidden flex flex-col justify-between h-48 transition-all ${
                mission.mission_type === 'Side'
                  ? 'hover:border-blue-500/50 hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]'
                  : 'hover:border-amber-500/50 hover:shadow-[0_0_30px_rgba(245,158,11,0.15)]'
              }`}
            >
              {basePath && (
                <img 
                  src={imageUrl}
                  alt={mission.name}
                  className="absolute inset-0 w-full h-full object-cover opacity-20 group-hover:opacity-40 transition-opacity"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              )}
              <div className={`absolute inset-0 bg-gradient-to-br to-transparent opacity-0 group-hover:opacity-100 transition-opacity ${
                mission.mission_type === 'Side' ? 'from-blue-500/5' : 'from-amber-500/5'
              }`} />
            <div className="relative z-10">
              <div className={`text-[10px] font-bold uppercase tracking-widest mb-2 flex items-center gap-2 ${mission.mission_type === 'Side' ? 'text-blue-500' : 'text-amber-500'}`}>
                <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${mission.mission_type === 'Side' ? 'bg-blue-500' : 'bg-amber-500'}`} />
                {mission.mission_type === 'Side' ? 'Side Mission' : 'Main Mission'}
              </div>
              <h3 className="text-xl font-bold text-white group-hover:text-amber-50 transition-colors leading-tight line-clamp-3">
                {mission.name.replace(/_/g, ' ')}
              </h3>
            </div>
            
            <div className="relative z-10 mt-4 flex justify-between items-end border-t border-white/5 pt-4">
              <div className={`text-[10px] text-zinc-500 font-mono uppercase tracking-widest transition-colors ${
                mission.mission_type === 'Side' ? 'group-hover:text-blue-500/60' : 'group-hover:text-amber-500/60'
              }`}>
                View Dossier ↗
              </div>
            </div>
          </motion.div>
        ); })}
        {missions.length === 0 && (
          <div className="col-span-full py-12 text-center text-white/30 font-mono text-sm uppercase tracking-widest border border-dashed border-white/10 rounded-xl">
            No active quests in this region.
          </div>
        )}
      </div>
    </div>
  );
}
