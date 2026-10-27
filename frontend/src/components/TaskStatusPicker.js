"use client";
import React from 'react';
export const TASK_STATUSES = [['pending', 'Pending'], ['in_progress', 'In progress'], ['deferred', 'Deferred'], ['cancelled', 'Cancelled'], ['done', 'Done']];
export default function TaskStatusPicker({ value = 'pending', label, disabled, onChange, id }) {
  const select = React.useRef(null);
  const restoreFocus = React.useRef(false);
  React.useEffect(() => {
    if (!disabled && restoreFocus.current) {
      select.current?.focus();
      restoreFocus.current = false;
    }
  }, [disabled]);
  return <select ref={select} id={id} aria-label={`Status: ${label}`} aria-busy={disabled || undefined}
    value={value === 'completed' ? 'done' : value} disabled={disabled}
    onChange={event => { restoreFocus.current = true; onChange(event.target.value); }}
    className="max-w-36 rounded border border-white/10 bg-zinc-950/90 px-2 py-1 text-xs text-[#00d4ff] backdrop-blur-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00d4ff] disabled:opacity-50">
    {value === 'completion_pending' && <option value="completion_pending" disabled>Saved — XP pending</option>}
    {TASK_STATUSES.map(([status, text]) => <option key={status} value={status}>{text}</option>)}
  </select>;
}
