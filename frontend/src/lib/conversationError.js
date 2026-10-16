export async function conversationError(response, fallback) {
  const text = await response.text();
  try {
    const body = JSON.parse(text);
    const message = body.detail || body.message;
    const error = new Error(typeof message === 'string' && message.trim() ? message : fallback);
    error.conversationMessage = true;
    return error;
  } catch {
    // HTML, tracebacks and malformed JSON are transport diagnostics, not UI copy.
    const error = new Error(fallback);
    error.conversationMessage = true;
    return error;
  }
}

export function conversationMessage(error, fallback) {
  return error?.conversationMessage ? error.message : fallback;
}
