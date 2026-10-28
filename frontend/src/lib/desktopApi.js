/** Shared boundary for web/dev HTTP calls and native Tauri commands. */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
export const OPERATION_EVENT = 'navis://operation';
export const VAULT_CHANGE_EVENT = 'navis://vault-change';

export function supportsLocalOllama() {
  if (isTauriRuntime()) return true;
  if (typeof window === 'undefined') return false;
  return ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
}

export function isTauriRuntime() {
  return typeof window !== 'undefined' && Boolean(window.__TAURI_INTERNALS__);
}

async function getInvoke() {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke;
}

export async function listenNativeEvent(eventName, handler) {
  if (!isTauriRuntime()) return () => {};
  const { listen } = await import('@tauri-apps/api/event');
  return await listen(eventName, (event) => handler(event?.payload !== undefined ? event.payload : event));
}

export async function listenVaultChange(handler) {
  return listenNativeEvent(VAULT_CHANGE_EVENT, handler);
}

/**
 * Connects to real-time vault change events across desktop and web runtimes.
 * - In desktop mode (Tauri): listens to native VAULT_CHANGE_EVENT.
 * - In web mode: connects to Server-Sent Events (SSE) at /api/events/stream.
 *
 * @param {Function|Object} handlerOrOptions Callback (payload) => void, or { onEvent, onConnectionChange }
 * @param {Object} [options] Optional options if first argument is callback: { onConnectionChange }
 * @returns {Function} Clean-up unlisten/disconnect function.
 */
export function subscribeVaultStream(handlerOrOptions, options = {}) {
  const handler = typeof handlerOrOptions === 'function' ? handlerOrOptions : handlerOrOptions?.onEvent;
  const onConnectionChange = typeof handlerOrOptions === 'object'
    ? handlerOrOptions.onConnectionChange
    : options.onConnectionChange;

  let active = true;
  let unlistenFn = null;

  if (isTauriRuntime()) {
    listenVaultChange((payload) => {
      if (active && handler) handler(payload);
    }).then((unlisten) => {
      if (!active) {
        if (typeof unlisten === 'function') unlisten();
        return;
      }
      unlistenFn = unlisten;
      if (onConnectionChange) onConnectionChange(true, 'connected');
    }).catch((err) => {
      console.error('Failed to listen to native vault change:', err);
      if (active && onConnectionChange) onConnectionChange(false, 'error');
    });

    return () => {
      active = false;
      if (typeof unlistenFn === 'function') {
        try { unlistenFn(); } catch (_) {}
      }
      if (onConnectionChange) onConnectionChange(false, 'disconnected');
    };
  }

  // Web mode: Server-Sent Events (SSE)
  if (typeof window !== 'undefined' && typeof window.EventSource !== 'undefined') {
    const streamUrl = apiUrl('/api/events/stream');
    let es = null;
    try {
      es = new window.EventSource(streamUrl);
    } catch (err) {
      console.error('Failed to initialize EventSource:', err);
      if (onConnectionChange) onConnectionChange(false, 'error');
      return () => {};
    }

    es.onopen = () => {
      if (active && onConnectionChange) onConnectionChange(true, 'connected');
    };

    es.onerror = () => {
      if (active && onConnectionChange) onConnectionChange(false, 'disconnected');
    };

    const handlePayload = (raw) => {
      if (!active || !handler) return;
      try {
        const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
        handler(parsed);
      } catch (err) {
        console.warn('Failed to parse SSE event data:', err);
      }
    };

    const onVaultChange = (evt) => handlePayload(evt.data);
    const onGenericMessage = (evt) => handlePayload(evt.data);

    es.addEventListener('vault_change', onVaultChange);
    es.addEventListener('message', onGenericMessage);

    return () => {
      active = false;
      try {
        es.removeEventListener('vault_change', onVaultChange);
        es.removeEventListener('message', onGenericMessage);
        es.close();
      } catch (_) {}
      if (onConnectionChange) onConnectionChange(false, 'disconnected');
    };
  }

  if (onConnectionChange) onConnectionChange(false, 'unsupported');
  return () => {};
}

export async function emitNativeVaultChangeEvent(event) {
  return invokeNative('emit_vault_change_event', { event });
}

export async function startLoungeOperation(operation) {
  return invokeNative('start_lounge_operation', { operation });
}

export async function cancelLoungeOperation(jobId) {
  return invokeNative('cancel_lounge_operation', { jobId });
}

export async function startP5Operation(operation) {
  return invokeNative('start_p5_operation', { operation });
}

export async function cancelP5Operation(jobId) {
  return invokeNative('cancel_p5_operation', { jobId });
}

export async function cancelSyncOperation(jobId) {
  return invokeNative('cancel_sync_operation', { jobId });
}

export async function emitNativeOperationEvent(event) {
  return invokeNative('emit_operation_event', { event });
}

export async function invokeNative(command, args = {}) {
  if (!isTauriRuntime()) {
    throw new Error(`Native command "${command}" is only available in Tauri runtime`);
  }
  const invoke = await getInvoke();
  return invoke(command, args);
}

class NativeResponse {
  constructor(result) {
    this.status = result.status;
    this.ok = result.status >= 200 && result.status < 300;
    this._body = result.body;
    this._text = result.text;
  }

  async json() { return this._body; }
  async text() { return this._text; }
}

// After dispatch, abort stops waiting; it does not roll back native writes or
// cancel jobs. Job cancellation requires an explicit cancel*Operation call.
function withAbort(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) {
    return Promise.reject(new DOMException('The operation was aborted.', 'AbortError'));
  }

  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('The operation was aborted.', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

function normalizeError(error, fallback = 'Native request failed') {
  if (error instanceof Error) return error;
  if (typeof error === 'string' && error.trim()) return new Error(error);
  if (error && typeof error.message === 'string' && error.message.trim()) return new Error(error.message);
  try {
    return new Error(JSON.stringify(error) || fallback);
  } catch {
    return new Error(fallback);
  }
}

export function apiUrl(path) {
  if (isTauriRuntime() && path.startsWith('vault://localhost/')) {
    return nativeVaultAssetUrl(path.slice('vault://localhost/'.length));
  }
  if (/^[a-z][a-z\d+.-]*:/i.test(path)) return path;
  if (isTauriRuntime() && path.startsWith('/api/vault/')) {
    return nativeVaultAssetUrl(path.slice('/api/vault/'.length));
  }
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

function nativeVaultAssetUrl(path) {
  const windowsOrAndroid = typeof navigator !== 'undefined' && /Windows|Android/i.test(navigator.userAgent);
  const hostPath = path.replace(/^\/+/, '');
  return windowsOrAndroid
    ? `http://vault.localhost/${hostPath}`
    : `vault://localhost/${hostPath}`;
}

export function vaultAssetUrl(assetPath, { cacheBust = false } = {}) {
  const encodedPath = assetPath
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/');
  const url = apiUrl(`/api/vault/${encodedPath}`);
  return cacheBust ? `${url}?t=${Date.now()}` : url;
}

async function performApiFetch(path, options = {}) {
  // Check before evaluating any transport promise, including polish and jobs.
  if (options.signal?.aborted) {
    throw new DOMException('The operation was aborted.', 'AbortError');
  }
  if (path.startsWith('/api/journal/brief/') && !supportsLocalOllama()) {
    throw new Error('Briefs require the desktop app or a local Navis server.');
  }
  if (path === '/api/journal/entry/polish' && !supportsLocalOllama()) {
    throw new Error('Local Ollama suggestions are available in the desktop app or when running Navis locally.');
  }
  if (isTauriRuntime() && path === '/api/journal/entry/polish') {
    let body = options.body;
    if (typeof body === 'string') {
      try { body = JSON.parse(body); } catch { body = {}; }
    }
    const result = await withAbort(invokeNative('polish_journal_entry', {
      entry: body?.entry || '',
      section: body?.section || 'sanctum',
    }), options.signal);
    return new NativeResponse(result);
  }
  if (isTauriRuntime() && path.startsWith('/api/')) {
    const nativeOperation = options.method === 'POST' && (
      path.startsWith('/api/sync') ? 'sync' :
      path.startsWith('/api/journal/rollover') ? 'rollover' : null
    );
    if (nativeOperation) {
      const result = await withAbort(
        invokeNative('start_sync_operation', {
          operation: nativeOperation,
          ...(new URLSearchParams(path.split('?')[1] || '').get('request_id')
            ? { requestId: new URLSearchParams(path.split('?')[1]).get('request_id') } : {}),
        }),
        options.signal,
      );
      return new NativeResponse({ status: 200, body: result, text: JSON.stringify(result) });
    }
    let body = options.body;
    if (typeof body === 'string') {
      try { body = JSON.parse(body); } catch { body = undefined; }
    }
    const command = path.startsWith('/api/v1/progression') ? 'progression_request' : path.startsWith('/api/v1/lounge') || path.startsWith('/api/v1/library') ? 'lounge_request' : path.startsWith('/api/battle') || path.startsWith('/api/missions/') || path.startsWith('/api/cache/') ? 'p3_request' : path.startsWith('/api/reid') || path.startsWith('/api/neural') || path.startsWith('/api/forge') || path.startsWith('/api/v1/biometrics') ? 'p5_request' : 'vault_request';
    let result;
    try {
      result = await withAbort(invokeNative(command, {
        path,
        method: options.method || 'GET',
        body: body || null,
      }), options.signal);
    } catch (error) {
      throw normalizeError(error);
    }
    return new NativeResponse(result);
  }
  if (typeof window !== 'undefined') {
    const savedKey = (typeof sessionStorage !== 'undefined' ? sessionStorage?.getItem('vanguard_key') : null) ||
                     (typeof localStorage !== 'undefined' ? localStorage?.getItem('vanguard_key') : null);
    if (savedKey) {
      const headers = new Headers(options.headers || {});
      if (!headers.has('Authorization') && !headers.has('X-Vanguard-Key')) {
        headers.set('X-Vanguard-Key', savedKey);
        return fetch(apiUrl(path), { ...options, headers });
      }
    }
  }
  return fetch(apiUrl(path), options);
}

export async function startupDiagnostics() {
  if (!isTauriRuntime()) return { runtime: 'web-dev', navis_root: null, overall_ok: true, checks: [] };
  return invokeNative('startup_diagnostics');
}

export async function healthcheck() {
  if (isTauriRuntime()) return invokeNative('healthcheck');
  const response = await fetch(apiUrl('/'), { headers: { Accept: 'application/json' } });
  return { mode: 'web', online: response.ok, status: response.status };
}

// Notify mounted consumers after writes that may change canonical XP.
export async function apiFetch(path, options = {}) {
  const response = await performApiFetch(path, options);
  if (response.ok && options.method && options.method !== 'GET' &&
      /^\/api\/(v1\/progression|journal|battle|sync)/.test(path) && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('navis:progression-changed'));
  }
  return response;
}
