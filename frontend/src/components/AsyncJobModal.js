'use client';
import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { apiFetch, cancelSyncOperation, isTauriRuntime, listenNativeEvent, OPERATION_EVENT } from '../lib/desktopApi';

export default function AsyncJobModal({ jobId, title, onClose, onComplete, operation }) {
  const structuredOperation = operation === 'sync' || operation === 'rollover';
  const [jobStatus, setJobStatus] = useState('running');
  const [outputLog, setOutputLog] = useState('Initializing connection...');
  const [waitingForNativeEvents, setWaitingForNativeEvents] = useState(false);
  const [outcome, setOutcome] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [retryToken, setRetryToken] = useState(0);
  const scrollRef = useRef(null);
  const statusRef = useRef('running');
  const outcomeRef = useRef(null);
  const completeRef = useRef(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    let isMounted = true;
    let timeoutId;
    let unlisten;
    let attempts = 0;

    const applyStatus = (data) => {
      if (!isMounted || (data.job_id && data.job_id !== jobId)) return;
      setWaitingForNativeEvents(false);
      // Durable step reports take precedence over coarse native process events.
      if (Array.isArray(data.steps)) {
        outcomeRef.current = data;
        setOutcome(data);
      }
      const durable = outcomeRef.current;
      const status = durable && (durable.status !== 'running' || durable.record_job_id !== jobId) ? durable.status : (data.status || 'running');
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
      if (status === 'completed' && (!durable || !durable.record_job_id || durable.record_job_id === jobId)
          && (!isTauriRuntime() || !structuredOperation || Array.isArray(data.steps))) {
        window.dispatchEvent(new Event('navis:progression-changed'));
        if (completeRef.current !== jobId) {
          completeRef.current = jobId;
          onCompleteRef.current?.(data);
        }
      }
    };

    const pollStatus = async () => {
      if (!isMounted) return;
      attempts++;
      try {
        const target = outcomeRef.current?.record_job_id || jobId;
        const res = await apiFetch(`/api/ops/jobs/${target}`);
        const value = res.ok ? await res.json() : null;
        if (structuredOperation && (!value || (!value.steps && value.status === 'failed'))) {
          const latest = await apiFetch('/api/ops/latest');
          if (!latest.ok) throw new Error('Saved operation status unavailable');
          const previous = await latest.json();
          applyStatus({ ...previous, record_job_id: previous.job_id, job_id: jobId });
        }
        else if (res.ok) applyStatus(Array.isArray(value.steps) ? { ...value, record_job_id: value.job_id, job_id: jobId } : value);
        else if (!isTauriRuntime()) throw new Error('Failed to fetch job status');
        else if (attempts >= 5 && !outcomeRef.current) throw new Error('Saved operation status unavailable');
      } catch (err) {
        if (!isMounted) return;
        if (!isTauriRuntime() || attempts >= 5) {
          statusRef.current = 'unavailable';
          setJobStatus('unavailable');
          setOutputLog(prev => `${prev}\n\n[POLLING ERROR] ${err.message}`);
          return;
        }
        setWaitingForNativeEvents(true);
      }
      if (isMounted && (statusRef.current === 'running' || (isTauriRuntime() && structuredOperation && !outcomeRef.current && attempts < 5))) timeoutId = setTimeout(pollStatus, 2000);
    };

    const setup = async () => {
      if (isTauriRuntime()) {
        try { unlisten = await listenNativeEvent(OPERATION_EVENT, applyStatus); }
        catch { setWaitingForNativeEvents(true); }
      }
      pollStatus();
    };
    setup();

    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
      if (unlisten) unlisten();
    };
  }, [jobId, retryToken, structuredOperation]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [outputLog]);

  const retry = () => {
    statusRef.current = 'running';
    setJobStatus('running');
    setOutputLog(prev => `${prev}\nReconnecting status...`);
    setWaitingForNativeEvents(false);
    setRetryToken(token => token + 1);
    // This reconnects reads only. Never replay possibly committed mutations.
  };

  const cancel = async () => {
    if (!isTauriRuntime()) return;
    try {
      await cancelSyncOperation(outcomeRef.current?.record_job_id || jobId);
      setOutputLog(prev => `${prev}\nCancellation requested...`);
    } catch (error) {
      setOutputLog(prev => `${prev}\nCancellation failed: ${error.message || error}`);
    }
  };

  const confirmReview = async () => {
    if (reviewing || !window.confirm('Confirm you reviewed the saved changes. This will not repeat any steps.')) return;
    setReviewing(true);
    setReviewError('');
    try {
      const target = outcomeRef.current?.record_job_id || jobId;
      const response = await apiFetch(`/api/ops/jobs/${target}/review`, { method: 'POST' });
      if (!response.ok) throw new Error('Review could not be recorded. Reconnect status before trying again.');
      const value = await response.json();
      const reviewed = { ...value, record_job_id: value.job_id, job_id: jobId };
      outcomeRef.current = reviewed;
      setOutcome(reviewed);
    } catch (error) { setReviewError(error.message || 'Review unavailable.'); }
    finally { setReviewing(false); }
  };

  const dialog = (
    <div role="dialog" aria-modal="true" aria-label={title || 'Executing Sequence'} className="fixed inset-0 z-[9999] bg-[#050505]/80 backdrop-blur-md flex items-center justify-center p-6">
      <div style={{ maxHeight: 'calc(100dvh - 3rem)' }} className="w-full min-w-0 max-w-2xl overflow-y-auto glass-dark p-6 rounded-lg border border-white/10 shadow-2xl flex flex-col space-y-4">
        <div className="flex justify-between items-center border-b border-white/5 pb-4">
          <div>
            <h2 className="text-xl font-bold text-white tracking-[0.2em] uppercase">{title || 'Executing Sequence'}</h2>
            <p className="text-[10px] text-white/40 uppercase tracking-widest mt-1">Job ID: {jobId}</p>
          </div>
          <div>
            {jobStatus === 'running' && <span className="text-accent text-[10px] uppercase tracking-widest animate-pulse">Running</span>}
            {jobStatus === 'completed' && <span className="text-green-400 text-[10px] uppercase tracking-widest font-bold">✔️ Completed</span>}
            {jobStatus === 'failed' && <span className="text-red-400 text-[10px] uppercase tracking-widest font-bold">❌ Failed</span>}
            {jobStatus === 'partial' && <span role="status" className="text-amber-300 text-xs">Partially completed</span>}
            {jobStatus === 'interrupted' && <span role="status" className="text-amber-300 text-xs">Interrupted — review saved changes</span>}
            {jobStatus === 'cancelled' && <span role="status" className="text-amber-300 text-xs">Cancelled — changes may have saved</span>}
            {jobStatus === 'unavailable' && <span role="alert" className="text-amber-300 text-xs">Status unavailable — saved changes unknown</span>}
          </div>
        </div>
        <div ref={scrollRef} className="bg-black/60 border border-white/5 p-4 rounded h-72 overflow-y-auto font-mono text-xs text-white/70 whitespace-pre-wrap leading-relaxed">{outputLog}</div>
        {outcome?.steps && (
          <section aria-label="Operation outcomes" className="space-y-2 text-xs">
            {outcome.record_job_id && outcome.record_job_id !== jobId && <p className="text-amber-200">Showing the previous operation. This request did not start.</p>}
            <ul className="space-y-1">
              {outcome.steps.map((step, index) => <li key={`${step.id}-${index}`} className="flex justify-between gap-3">
                <span>{step.label}</span><span>{step.status.replaceAll('_', ' ')}{step.persistence === 'confirmed' ? ' · saved' : ''}</span>
              </li>)}
            </ul>
            {outcome.recovery === 'review_saved_changes' && <p role="alert" className="text-amber-200">{outcome.reviewed ? 'Review recorded. No steps were repeated.' : 'Changes may already be saved. Review the listed steps before starting another operation. No steps will be repeated automatically.'}</p>}
            {reviewError && <p role="alert" className="text-red-300">{reviewError}</p>}
          </section>
        )}
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
          {['failed', 'partial', 'interrupted', 'cancelled', 'unavailable'].includes(jobStatus) && <button onClick={retry} className="px-6 py-2 bg-white/5 hover:bg-white/10 border border-white/20 rounded text-white text-xs font-bold uppercase tracking-[0.2em]">Reconnect status</button>}
          {outcome?.recovery === 'review_saved_changes' && !outcome.reviewed && <button onClick={confirmReview} disabled={reviewing} className="px-4 py-2 bg-amber-500/10 border border-amber-400/30 rounded text-amber-200 text-xs">{reviewing ? 'Recording review...' : 'Confirm review'}</button>}
          {jobStatus !== 'running' ? <button onClick={onClose} className="px-6 py-2 bg-accent/10 hover:bg-accent/20 border border-accent/40 rounded text-accent text-xs font-bold uppercase tracking-[0.2em]">Close Bridge</button> : isTauriRuntime() ? <button onClick={cancel} className="px-6 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/40 rounded text-red-300 text-xs font-bold uppercase tracking-[0.2em]">Cancel operation</button> : <button disabled className="px-6 py-2 bg-white/5 border border-white/10 rounded text-white/30 text-xs font-bold uppercase tracking-[0.2em] cursor-not-allowed">Sequence Lock Active</button>}
        </div>
      </div>
    </div>
  );
  return typeof document !== 'undefined' && document.body ? createPortal(dialog, document.body) : dialog;
}
