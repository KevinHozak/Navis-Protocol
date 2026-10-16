import test from 'node:test';
import assert from 'node:assert/strict';
import { isPrivatePath } from './publication-policy.mjs';

test('blocks private exports, local Vault data, keys, credentials, and backups', () => {
  for (const file of [
    'backend/metadata.jsonl', 'backend/search_results.json', 'sync_output.txt',
    '.env', 'backend/.env.production', '.envrc', 'backend/oauth-token.json',
    'secrets.json', 'saved_credentials.json', 'token.json', 'service-account.json',
    'private.pem', 'signing.p8', 'credentials.pkcs12', 'session.db-wal',
    'state.sqlite3-shm', 'logs/runtime.log', 'trace.stackdump',
    'saved.bundle', 'vault.zip', 'state.dump', 'journal.md.backup_1200',
    '.publication/recovery/data.json', '.worktrees/branch/file.py',
    '.test-fixture/Journal/day.md', 'Journal/2026/10/day.md', 'Bridge/status.json',
    'Keeper/profile.json', '.ssh/id_rsa', '.aws/credentials',
  ]) assert.equal(isPrivatePath(file), true, file);
});

test('allows source, lockfiles, synthetic fixtures, and environment examples', () => {
  for (const file of [
    'backend/services/library_service.py', 'frontend/package-lock.json',
    'docs/fixtures/weekly-infographic-synthetic.json', '.env.example',
    'backend/.env.local.example', 'frontend/public/assets/companions/dusk.png',
    'frontend/src-tauri/tests/fixtures/p3_parity.json', 'README.md',
  ]) assert.equal(isPrivatePath(file), false, file);
});
