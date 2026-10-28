import { execFileSync } from 'node:child_process';
import { test } from 'vitest';

test('canonical coverage refresh, filtering, and safe rendering', () => {
  execFileSync(process.execPath, ['static/quality-coverage.test.mjs'], { cwd: process.cwd() });
});
