export const SUPPORTED_MAP_NODE_TYPES = new Set(['Town', 'Camp', 'Dungeon', 'Boss']);

/** Validate source map nodes while retaining their original order. */
export function validateMapNodes(data) {
  const sourceNodes = Array.isArray(data?.nodes) ? data.nodes : [];
  const hasNodeList = Array.isArray(data?.nodes);
  const nodes = [];
  let skipped = 0;

  sourceNodes.forEach((node) => {
    const valid = node &&
      typeof node === 'object' &&
      Number.isFinite(node.x) &&
      Number.isFinite(node.y) &&
      typeof node.name === 'string' &&
      node.name.trim().length > 0 &&
      SUPPORTED_MAP_NODE_TYPES.has(node.type);

    if (valid) nodes.push({ ...node, name: node.name.trim() });
    else skipped += 1;
  });

  return { nodes, skipped, hasNodeList };
}

/** Describe map loading outcomes without hiding image failures or inventing nodes. */
export function describeMapLoad({ mapData, dataLoadError, imageLoadError } = {}) {
  const validation = validateMapNodes(mapData);
  let kind = 'ready';
  let message = '';
  if (dataLoadError) {
    if (dataLoadError.status === 200) {
      kind = 'invalid-json';
      message = 'Overworld.json was found but could not be parsed. Fix its JSON syntax, then retry.';
    } else {
      const status = Number.isInteger(dataLoadError.status) && dataLoadError.status > 0
        ? ` (HTTP ${dataLoadError.status})`
        : '';
      kind = 'data-unavailable';
      message = `Overworld data could not be loaded${status}. Check the selected realm's Realms folder and Vault access, then retry.`;
    }
  } else if (!validation.hasNodeList) {
    kind = 'invalid-schema';
    message = 'Overworld.json must contain a nodes array. Correct the file schema, then retry.';
  } else if (validation.nodes.length === 0 && validation.skipped > 0) {
    kind = 'invalid-nodes';
    message = `No usable Overworld nodes were found; ${validation.skipped} invalid ${validation.skipped === 1 ? 'entry was' : 'entries were'} skipped. Each node needs a name, supported type, and finite x/y coordinates.`;
  } else if (validation.nodes.length === 0) {
    kind = 'empty';
    message = 'Overworld.json is valid but has no nodes. Add destinations to the selected realm, or retry after updating the file.';
  } else if (validation.skipped > 0) {
    kind = 'invalid-nodes';
    message = `${validation.skipped} invalid map ${validation.skipped === 1 ? 'entry was' : 'entries were'} skipped. Valid destinations remain available.`;
  }

  if (imageLoadError) {
    const status = Number.isInteger(imageLoadError.status) && imageLoadError.status > 0
      ? ` (HTTP ${imageLoadError.status})`
      : '';
    const imageMessage = `Overworld.png could not be loaded${status}. Check the selected realm's image file and Vault access, then retry.`;
    if (kind === 'ready') kind = 'image-unavailable';
    message = [message, imageMessage].filter(Boolean).join(' ');
  }
  return { ...validation, kind, message };
}
