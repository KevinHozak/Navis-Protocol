'use client';
import { motion, AnimatePresence } from 'framer-motion';

export default function BanterBubble({ activeBanter, onClose }) {
  return (
    <AnimatePresence>
      {activeBanter && (
        <motion.div
          initial={{ opacity: 0, y: 50, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.9 }}
          transition={{ type: 'spring', damping: 20, stiffness: 100 }}
          className="fixed bottom-24 left-12 z-[9999] max-w-sm pointer-events-none"
        >
          <div className="glass-dark p-4 rounded-xl border border-white/20 shadow-2xl relative overflow-hidden backdrop-blur-md">
            {/* Gloss reflection line */}
            <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-white/40 to-transparent"></div>
            
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 mt-1">
                <div className="w-8 h-8 rounded bg-accent/20 border border-accent/40 flex items-center justify-center text-accent font-bold uppercase text-[10px] tracking-wider shadow-[0_0_10px_rgba(61,177,255,0.2)]">
                  {activeBanter.speaker.substring(0, 2)}
                </div>
              </div>
              <div>
                <p className="text-[10px] font-bold text-accent uppercase tracking-[0.2em] mb-1 opacity-90 drop-shadow-sm">
                  {activeBanter.speaker}
                </p>
                <p className="text-xs text-white/90 leading-relaxed font-serif italic drop-shadow-sm">
                  &quot;{activeBanter.quote}&quot;
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
