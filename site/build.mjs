// Build the GitHub Pages site into _site/.
//
//   node site/build.mjs              copy site/ plus every repo file index.html references under projects/
//   node site/build.mjs --list-lfs   print those referenced videos, comma-separated (for `git lfs pull --include`)
//
// index.html is the single source of truth: add a video or thumbnail there with its repo path
// (projects/...) and the build and the Pages workflow pick it up.
import { closeSync, cpSync, existsSync, mkdirSync, openSync, readFileSync, readSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(SITE, '..');
const OUT = join(ROOT, '_site');
const DEV_ONLY = new Set(['build.mjs', 'serve.mjs']);

const html = readFileSync(join(SITE, 'index.html'), 'utf8');
const refs = [...new Set([...html.matchAll(/["'](projects\/[^"']+)["']/g)].map((m) => m[1]))].sort();
const videos = refs.filter((p) => /\.(mp4|webm|mov)$/i.test(p));

if (process.argv.includes('--list-lfs')) {
  console.log(videos.join(','));
  process.exit(0);
}

// A Git LFS pointer is a ~130-byte text file starting with this line.
function isLfsPointer(file) {
  const fd = openSync(file, 'r');
  const head = Buffer.alloc(40);
  readSync(fd, head, 0, head.length, 0);
  closeSync(fd);
  return head.toString('utf8').startsWith('version https://git-lfs');
}

rmSync(OUT, { recursive: true, force: true });
cpSync(SITE, OUT, { recursive: true, filter: (src) => !DEV_ONLY.has(src.split(/[\\/]/).pop()) });

let bytes = 0;
for (const rel of refs) {
  const src = join(ROOT, rel);
  if (!existsSync(src)) throw new Error(`index.html references ${rel}, which does not exist`);
  if (isLfsPointer(src)) throw new Error(`${rel} is still a Git LFS pointer; run git lfs pull first`);
  const dest = join(OUT, rel);
  mkdirSync(dirname(dest), { recursive: true });
  cpSync(src, dest);
  bytes += statSync(src).size;
}
writeFileSync(join(OUT, '.nojekyll'), '');

console.log(`_site/ built: ${refs.length} files from projects/ (${videos.length} videos, ${(bytes / 1048576).toFixed(1)} MB)`);
