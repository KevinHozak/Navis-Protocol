// Shared request lifecycle for active and recurring boards. No optimistic writes.
export function createTaskBoardStore(apiFetch, endpoint, area) {
  let state = { tasks: [], loading: true, listError: '', mutationError: '', pending: false, loaded: false };
  let revision = 0;
  let disposed = false;
  let locked = false;
  let uncertainCreate = null;
  const listeners = new Set();
  const publish = (patch) => {
    if (disposed) return;
    state = { ...state, ...patch };
    listeners.forEach(listener => listener(state));
  };
  const list = async () => {
    const response = await apiFetch(`${endpoint}${endpoint.includes('?') ? '&' : '?'}area=${encodeURIComponent(area)}`);
    if (!response.ok) throw new Error('Unable to load tasks. Retry to reconnect.');
    const data = await response.json();
    if (!Array.isArray(data) || data.some(task => !task || typeof task !== 'object'
      || typeof task.id !== 'string' || typeof task.text !== 'string'
      || ['next_due', 'last_done', 'created_at', 'frequency'].some(key => task[key] != null && typeof task[key] !== 'string'))) {
      throw new Error('Invalid task response. Retry to reconnect.');
    }
    return data;
  };
  const refresh = async () => {
    if (disposed) return;
    const request = ++revision;
    publish({ loading: true, listError: '' });
    try {
      const tasks = await list();
      if (request === revision) publish({ tasks, loaded: true });
    } catch (error) {
      if (request === revision) publish({ listError: error?.message || 'Unable to load tasks. Retry to reconnect.' });
    } finally {
      if (request === revision) publish({ loading: false });
    }
  };
  const mutate = async (path, options, label, create = null, verify = null) => {
    if (locked || disposed || !state.loaded || state.loading || state.listError) return false;
    locked = true;
    ++revision; // A pre-write list cannot overwrite the post-write refresh.
    publish({ pending: true, loading: false, mutationError: '' });
    try {
      // A rejected response may have followed a committed create. Read back
      // before another POST, including when the user edited the failed draft.
      if (create && uncertainCreate) {
        const tasks = await list();
        if (disposed) return false;
        const recovered = tasks.some(task => !uncertainCreate.ids.has(task.id)
          && task.text === uncertainCreate.task.text
          && (!uncertainCreate.task.frequency || task.frequency === uncertainCreate.task.frequency));
        const sameDraft = create && create.text === uncertainCreate.task.text
          && create.frequency === uncertainCreate.task.frequency;
        publish({ tasks, loaded: true, listError: '' });
        uncertainCreate = null;
        if (recovered && sameDraft) return true;
      }
      if (disposed) return false;
      if (create) uncertainCreate = { task: { ...create }, ids: new Set(state.tasks.map(task => task.id)) };
      const response = await apiFetch(path, options);
      if (!response.ok) {
        let detail;
        try { detail = (await response.json())?.detail; } catch { /* HTML/empty errors are supported. */ }
        throw new Error(typeof detail === 'string' ? detail : `${label} failed. Retry the action.`);
      }
      if (create) uncertainCreate = null;
      await refresh();
      if (verify && (state.listError || !verify(state.tasks))) throw new Error('Persisted status could not be verified. Reload before retrying.');
      return !disposed;
    } catch (error) {
      publish({ mutationError: `${label}: ${error?.message || 'Request interrupted. Retry the action.'}` });
      return false;
    } finally {
      locked = false;
      publish({ pending: false });
    }
  };
  return {
    getState: () => state,
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    refresh,
    mutate,
    dispose: () => { disposed = true; ++revision; listeners.clear(); },
  };
}
