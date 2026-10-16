import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const view = readFileSync('src/components/SectorView.js', 'utf8');
assert.match(view, /const \[banterHistoryError, setBanterHistoryError\] = useState\(null\)/);
assert.match(view, /const \[banterError, setBanterError\] = useState\(null\)/);
assert.match(view, /if \(!res\.ok\)[\s\S]*throw new Error\(error\.detail/);
assert.match(view, /setBanter\(data\);[\s\S]*setBanterHistoryError\(null\)/);
assert.match(view, /finally \{\s*setGeneratingBanter\(false\);\s*\}/);
assert.match(view, /Retry loading the feed/);
assert.match(view, /Retry resonance/);
assert.match(view, /No squad banter history yet/);
assert.doesNotMatch(view, /alert\(data\.detail|alert\("Resonance failed"\)/);
assert.match(view, /const \[banter, setBanter\] = useState\(\[\]\)/, 'the feed must not begin with fabricated history');

const native = readFileSync('src-tauri/src/p5.rs', 'utf8');
assert.ok(native.includes("strip_prefix('\\u{feff}')"));
assert.match(native, /Squad status is missing/);
assert.match(native, /Squad status could not be read/);
assert.match(native, /Squad status is malformed/);
assert.match(native, /fn banter_status_accepts_utf8_bom_and_empty_squad/);
assert.match(native, /fn banter_status_reports_missing_unreadable_and_malformed_files/);

const backend = readFileSync('../backend/main.py', 'utf8');
assert.match(backend, /encoding="utf-8-sig"[\s\S]*json\.load\(status_file\)/);
assert.match(backend, /Local banter generation failed[\s\S]*No online fallback was used/);
console.log('Banter recovery and error-state contracts passed.');
