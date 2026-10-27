"use client";

import { motion } from 'framer-motion';

export default function JournalSaveNotice({ receipt, retrying, onOpen, onRetryXP, onDismiss }) {
  if (!receipt) return null;
  return <motion.div role="status" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="fixed bottom-16 left-4 z-50 max-w-md rounded border border-cyan-400/30 bg-zinc-950/90 p-3 text-sm text-cyan-100 backdrop-blur-md">
    <p>{receipt.verified ? `Entry saved to ${receipt.date}.${receipt.xp_status === 'pending' ? ' XP sync pending.' : ''}` : `Save not verified for ${receipt.date}. Review the journal before retrying.`}</p>
    {receipt.viewRefreshError && <p className="text-amber-200">Entry saved; view refresh not verified. Open the saved journal to review.</p>}
    {receipt.retryError && <p className="text-amber-200">XP recovery not verified. The entry remains saved; review before retrying.</p>}
    <div className="mt-2 flex flex-wrap gap-3 text-xs">
      <button type="button" onClick={onOpen} className="text-cyan-300 underline">{receipt.verified ? 'Open saved journal' : 'Review journal'}</button>
      {receipt.verified && receipt.xp_status === 'pending' && receipt.request && <button type="button" disabled={retrying} onClick={onRetryXP} className="text-amber-200 underline disabled:opacity-40">{retrying ? 'Checking XP…' : 'Retry XP for saved entry'}</button>}
      <button type="button" onClick={onDismiss} className="text-zinc-400">Dismiss</button>
    </div>
  </motion.div>;
}
