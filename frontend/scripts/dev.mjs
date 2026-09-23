import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

const root = fileURLToPath(new URL('../', import.meta.url));
const repo = fileURLToPath(new URL('../../', import.meta.url));
const dataPort = process.env.VRK_DATA_PORT || '8793';
const children = [];
let stopping = false;

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
  process.exitCode = code;
}

function start(command, args, cwd) {
  const child = spawn(command, args, { cwd, stdio: 'inherit', env: process.env });
  children.push(child);
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (!stopping) stop(code || 0); });
  return child;
}

process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
const astroPackage = JSON.parse(readFileSync(new URL('../node_modules/astro/package.json', import.meta.url), 'utf8'));
const astroBin = fileURLToPath(new URL(`../node_modules/astro/${astroPackage.bin.astro}`, import.meta.url));
start(process.env.PYTHON || 'python3', ['scripts/serve_dashboard.py', dataPort], repo);
// This launcher owns both child processes. Astro 7 auto-detaches when run by
// an agent; --ignore-lock keeps it in the foreground so the data server has
// the same lifetime as the dev UI, including when Codex starts the preview.
start(process.execPath, [astroBin, 'dev', '--ignore-lock', ...process.argv.slice(2)], root);
