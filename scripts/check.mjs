import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const files = directory => readdirSync(path.join(root, directory), { withFileTypes: true }).flatMap(item => item.isDirectory() ? files(path.join(directory, item.name)) : /\.(?:js|mjs)$/.test(item.name) ? [path.join(directory, item.name)] : []);
for (const file of [...files('src'), ...files('scripts')]) {
  const result = spawnSync(process.execPath, ['--check', file], { cwd: root, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
const tests = readdirSync(path.join(root, 'tests')).filter(file => file.endsWith('.test.mjs')).map(file => path.join('tests', file));
const result = spawnSync(process.execPath, ['--test', ...tests], { cwd: root, stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);

