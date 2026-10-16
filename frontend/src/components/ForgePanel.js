'use client';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import AsyncJobModal from './AsyncJobModal';
import { apiFetch } from '@/lib/desktopApi';

export default function ForgePanel({ initialType = 'Companion' }) {
  const [entityType, setEntityType] = useState(initialType);
  const [name, setName] = useState('');

  useEffect(() => {
    setEntityType(initialType);
  }, [initialType]);
  
  const [prompt, setPrompt] = useState('');
  const [blueprint, setBlueprint] = useState(null);
  const [proposal, setProposal] = useState(null);
  const [loading, setLoading] = useState(false);
  const [manifesting, setManifesting] = useState(false);
  const [result, setResult] = useState(null);
  const [activeJob, setActiveJob] = useState(null);

  const submitForge = async () => {
    if (!name || !prompt) return;
    setLoading(true);
    setResult(null);
    setBlueprint(null);
    try {
      const res = await apiFetch('/api/forge/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_type: entityType, name, prompt })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setBlueprint(data.blueprint);
        setProposal({ id: data.proposal_id, target: data.target });
      } else {
        setResult(typeof data.detail === 'string' ? data.detail : 'Error generating blueprint.');
      }
    } catch (err) {
      console.error(err);
      setResult('Connection failed.');
    }
    setLoading(false);
  };

  const approveForge = async () => {
    if (!blueprint || !proposal) return;
    setManifesting(true);
    try {
      const res = await apiFetch('/api/forge/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposal.id, approved: true })
      });
      const data = await res.json();
      if (data.status === 'success' && data.job_id) {
        setActiveJob({ id: data.job_id, title: `Forging ${entityType}: ${name}` });
      } else if (data.status === 'success') {
        setResult('Manifestation Complete: ' + data.message);
        setBlueprint(null);
        setName('');
        setPrompt('');
      } else {
        setResult(typeof data.detail === 'string' ? data.detail : 'Error manifesting.');
      }
    } catch (err) {
      console.error(err);
      setResult('Connection failed during manifestation.');
    }
    setManifesting(false);
  };

  const handleJobComplete = () => {
    setResult('Manifestation Complete');
    setBlueprint(null);
    setName('');
    setPrompt('');
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col h-full bg-zinc-950/90 backdrop-blur-md border border-white/10 rounded-lg overflow-hidden p-4 text-slate-200 space-y-4 relative">
      <div className="font-bold text-orange-400 flex items-center text-xl mb-2">
        <span className="mr-2">🛠️</span> The Forge
      </div>

      
      {!blueprint ? (
        <div className="space-y-4 flex-1">
          <div>
            <label className="block text-sm font-bold text-slate-400 mb-1">Entity Type</label>
            <div className="w-full bg-slate-800/50 border border-slate-700 rounded p-2 text-slate-300 font-mono text-sm">
              {entityType}
            </div>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-400 mb-1">Name</label>
            <input 
              type="text" value={name} disabled={loading} onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded p-2 text-white focus:outline-none focus:border-orange-500"
              placeholder="e.g. Eldrin the Wise"
            />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-400 mb-1">Concept / Prompt</label>
            <textarea 
              value={prompt} disabled={loading} onChange={(e) => setPrompt(e.target.value)} rows={4}
              className="w-full bg-slate-800 border border-slate-600 rounded p-2 text-white focus:outline-none focus:border-orange-500"
              placeholder="Describe the entity in detail..."
            />
          </div>
          <button 
            onClick={submitForge} disabled={loading || !name || !prompt}
            className="w-full py-2 bg-orange-600 hover:bg-orange-500 disabled:bg-slate-700 text-white font-bold rounded flex justify-center items-center"
          >
            {loading ? 'Blueprinting...' : 'Generate Blueprint'}
          </button>
          {result && <div className="text-green-400 mt-2 p-2 bg-slate-800 rounded">{result}</div>}
        </div>
      ) : (
        <div className="space-y-4 flex-1 flex flex-col">
          <div className="font-bold text-slate-300">Blueprint Review: {name}</div>
          <p className="text-sm text-amber-300">Preview only. Approval writes to {proposal?.target}. Artwork generation is separate.</p>
          <pre className="flex-1 overflow-auto bg-slate-800 p-3 rounded border border-slate-600 text-xs">
            {JSON.stringify(blueprint, null, 2)}
          </pre>
          {result && <div role="status">{result}</div>}
          <div className="flex space-x-2">
            <button 
              onClick={async () => {
                try {
                  const res = await apiFetch('/api/forge/discard', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ proposal_id: proposal.id })
                  });
                  if (!res.ok) throw new Error('Discard failed');
                  setBlueprint(null); setProposal(null);
                } catch { setResult('Could not discard proposal. Retry.'); }
              }} disabled={manifesting || Boolean(activeJob)}
              className="flex-1 py-2 bg-slate-600 hover:bg-slate-500 text-white font-bold rounded"
            >
              Discard
            </button>
            <button 
              onClick={approveForge} disabled={manifesting || Boolean(activeJob)}
              className="flex-1 py-2 bg-orange-600 hover:bg-orange-500 disabled:bg-slate-700 text-white font-bold rounded"
            >
              {manifesting ? 'Manifesting...' : 'Approve & Manifest'}
            </button>
          </div>
        </div>
      )}

      {activeJob && (
        <AsyncJobModal 
          jobId={activeJob.id} 
          title={activeJob.title}
          onClose={() => setActiveJob(null)}
          onComplete={handleJobComplete}
        />
      )}
    </motion.div>
  );
}
