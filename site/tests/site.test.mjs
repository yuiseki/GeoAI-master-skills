import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (name) => readFile(path.join(root, name), 'utf8');

test('Wrangler は公開用 Worker にデプロイする', async () => {
  const config = JSON.parse(await read('wrangler.jsonc'));
  assert.equal(config.name, 'geoai-yuiseki-net');
  assert.equal(config.assets.directory, './dist');
  assert.equal(config.workers_dev, true);
});

test('公開記事は選定済みの二件だけで、出典と限界を持つ', async () => {
  const entries = [
    'src/content/reports/bus-operator-concentration.md',
    'src/content/reports/akita-bear-risk.md',
  ];
  assert.deepEqual((await readdir(path.join(root, 'src/content/reports'))).sort(), entries.map((entry) => path.basename(entry)).sort());
  for (const entry of entries) {
    const markdown = await read(entry);
    assert.match(markdown, /source: https:\/\/github\.com\/yuiseki\/GeoAI-master-skills\/blob\/main\/projects\//);
    assert.match(markdown, /## 限界/);
    assert.match(markdown, /図の出典:/);
  }
  assert.match(await read(entries[0]), /```math/);
  assert.match(await read(entries[1]), /```mermaid/);
});

test('ビルド後の数式・Mermaid・図は公開用ページで参照できる', async () => {
  const bus = await read('dist/reports/bus-operator-concentration/index.html');
  const bear = await read('dist/reports/akita-bear-risk/index.html');
  assert.match(bus, /class="katex/);
  assert.match(bear, /class="mermaid"/);
  assert.doesNotMatch(bus + bear, /href="\/GeoAI-master-skills\//);
  await stat(path.join(root, 'dist/images/bus-operator-share.png'));
  await stat(path.join(root, 'dist/images/akita-risk-map.png'));
  await stat(path.join(root, 'dist/favicon.svg'));
});
