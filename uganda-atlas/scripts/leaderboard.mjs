// Computes the editathon leaderboard and writes it to a file.
//   node scripts/leaderboard.mjs [output.json]
// Run on a schedule by .github/workflows/leaderboard.yml; the page reads the result as a quick first view
// and then refreshes itself live from the Wikimedia APIs.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { computeBoard, buildContext, SMALL_LISTS } from '../editathon/board.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const rd = p => JSON.parse(readFileSync(join(root, p), 'utf-8'));
const config = rd('editathon/config.json');
const users = rd('editathon/participants.json').participants || [];
const index = rd('editathon/tasks/index.json');
const loaded = {};
for (const l of index.lists) if (SMALL_LISTS.includes(l.id)) {
  loaded[l.id] = [];
  for (let n = 0; n < l.chunks; n++) loaded[l.id].push(...rd(`editathon/tasks/${l.id}.${n}.json`));
}
const ctx = buildContext(index, loaded);
const ua = { 'User-Agent': 'UgandaAtlasEditathon/1.0 (https://kasozidenis.github.io/uganda-atlas/; wikimedia community user group uganda)' };
const fetchFn = url => fetch(url, { headers: ua });
const board = await computeBoard({ config, users, ctx, fetchFn });
const out = process.argv[2] || join(root, 'leaderboard.json');
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(board));
console.log(`${board.state}: ${board.totals.participants} participants, ${board.totals.edits} counted edits, ${board.errors.length} errors`);
if (board.errors.length) console.log(board.errors.join('\n'));
