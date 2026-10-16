'use client';
import { useState, useEffect, useRef } from 'react';
import { apiFetch, cancelSyncOperation, isTauriRuntime, listenNativeEvent, OPERATION_EVENT } from '../lib/desktopApi';

export default function AsyncJobModal({ jobId, title, onClose, onComplete, onRetry }) {
  const [jobStatus, setJobStatus] = useState('running');
  const [outputLog, setOutputLog] = useState('Initializing connection...');
  const [waitingForNativeEvents, setWaitingForNativeEvents] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const scrollRef = useRef(null);
  const statusRef = useRef('running');

  useEffect(() => {
    let isMounted = true;
    let timeoutId;
    let unlisten;

    const applyStatus = (data) => {
      if (!isMounted || (data.job_id && data.job_id !== jobId)) return;
      setWaitingForNativeEvents(false);
      const status = data.status || 'running';
      statusRef.current = status;
      setJobStatus(status);
      if (data.output) {
        setOutputLog(data.output);
      } else if (data.message) {
        setOutputLog(prev => {
          if (!prev || prev === 'Initializing connection...' || prev === 'Retrying operation status connection...') {
            return data.message;
          }
          return `${prev}\n${data.message}`;
        });
      }
      if (status === 'completed') {
        window.dispatchEvent(new Event('navis:progression-changed'));
        if (onComplete) onComplete(data);
      }
    };

    const pollStatus = async () => {
      if (!isMounted || statusRef.current !== 'running') return;
      try {
        const res = await apiFetch(`/api/ops/jobs/${jobId}`);
        if (res.ok) applyStatus(await res.json());
        else if (!isTauriRuntime()) throw new Error('Failed to fetch job status');
      } catch (err) {
        if (!isMounted) return;
        if (!isTauriRuntime()) {
          statusRef.current = 'failed';
          setJobStatus('failed');
          setOutputLog(prev => `${prev}\n\n[POLLING ERROR] ${err.message}`);
          return;
        }
        setWaitingForNativeEvents(true);
      }
      if (isMounted && statusRef.current === 'running') timeoutId = setTimeout(pollStatus, 2000);
    };

    const setup = async () => {
      if (isTauriRuntime()) {
        unlisten = await listenNativeEvent(OPERATION_EVENT, applyStatus);
      }
      pollStatus();
    };
    setup();

    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
      if (unlisten) unlisten();
    };
  }, [jobId, onComplete, retryToken]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [outputLog]);

  const retry = () => {
    statusRef.current = 'running';
    setJobStatus('running');
    setOutputLog('Retrying operation status connection...');
    setWaitingForNativeEvents(false);
    setRetryToken(token => token + 1);
    if (onRetry) onRetry();
  };

  const cancel = async () => {
    if (!isTauriRuntime() || !jobId.startsWith('native-')) return;
    try {
      await cancelSyncOperation(jobId);
      setOutputLog(prev => `${prev}\nCancellation requested...`);
    } catch (error) {
      setOutputLog(prev => `${prev}\nCancellation failed: ${error.message || error}`);
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] bg-[#050505]/80 backdrop-blur-md flex items-center justify-center p-6">
      <div className="w-full max-w-2xl glass-dark p-6 rounded-lg border border-white/10 shadow-2xl flex flex-col space-y-4">
        <div className="flex justify-between items-center border-b border-white/5 pb-4">
          <div>
            <h2 className="text-xl font-bold text-white tracking-[0.2em] uppercase">{title || 'Executing Sequence'}</h2>
            <p className="text-[10px] text-white/40 uppercase tracking-widest mt-1">Job ID: {jobId}</p>
          </div>
          <div>
            {jobStatus === 'running' && <span className="text-accent text-[10px] uppercase tracking-widest animate-pulse">Running</span>}
            {jobStatus === 'completed' && <span className="text-green-400 text-[10px] uppercase tracking-widest font-bold">✔️ Completed</span>}
            {jobStatus === 'failed' && <span className="text-red-400 text-[10px] uppercase tracking-widest font-bold">❌ Failed</span>}
          </div>
        </div>
        <div ref={scrollRef} className="bg-black/60 border border-white/5 p-4 rounded h-72 overflow-y-auto font-mono text-xs text-white/70 whitespace-pre-wrap leading-relaxed">{outputLog}</div>
        {waitingForNativeEvents && (
          <div role="status" aria-live="polite" className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-accent/70">
            <span className="relative flex h-2 w-2" aria-hidden="true">
              <span className="absolute inline-flex h-full w-full rounded-full bg-accent/70 animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            <span>Waiting for native operation events</span>
            <span className="inline-flex w-5 justify-start" aria-hidden="true">
              <span className="animate-pulse">•••</span>
            </span>
          </div>
        )}
        <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
          {jobStatus === 'failed' && <button onClick={retry} className="px-6 py-2 bg-white/5 hover:bg-white/10 border border-white/20 rounded text-white text-xs font-bold uppercase tracking-[0.2em]">Retry</button>}
          {jobStatus !== 'running' ? <button onClick={onClose} className="px-6 py-2 bg-accent/10 hover:bg-accent/20 border border-accent/40 rounded text-accent text-xs font-bold uppercase tracking-[0.2em]">Close Bridge</button> : jobId.startsWith('native-') ? <button onClick={cancel} className="px-6 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/40 rounded text-red-300 text-xs font-bold uppercase tracking-[0.2em]">Cancel operation</button> : <button disabled className="px-6 py-2 bg-white/5 border border-white/10 rounded text-white/30 text-xs font-bold uppercase tracking-[0.2em] cursor-not-allowed">Sequence Lock Active</button>}
        </div>
      </div>
    </div>
  );
}
