import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../src/components/SovereignRibbon.js', import.meta.url), 'utf8');

const requiredIcons = ['Satellite', 'Castle', 'BookOpen', 'RefreshCw', 'Settings2'];
for (const icon of requiredIcons) {
  if (!source.includes(icon)) {
    throw new Error(`Top navigation is missing the ${icon} SVG icon.`);
  }
}

if (/\p{Extended_Pictographic}/u.test(source)) {
  throw new Error('Top navigation must not contain platform-dependent emoji glyphs.');
}

if (!source.includes('NAV_ICONS[item.id] || CircleHelp')) {
  throw new Error('Top navigation must provide a deterministic icon fallback.');
}

if (!source.includes('var(--accent)') || !source.includes('drop-shadow(0 0 5px var(--accent))')) {
  throw new Error('Top navigation icons must use the active theme accent for their glow.');
}

console.log('Top navigation icon regression check passed.');
