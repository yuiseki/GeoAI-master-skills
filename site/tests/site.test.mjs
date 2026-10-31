import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (name) => readFile(path.join(root, name), 'utf8');

test('公開 Markdown は技術文書と AI 文体の両プリセットで検査する', async () => {
  const pkg = JSON.parse(await read('package.json'));
  const config = JSON.parse(await read('.textlintrc.json'));
  assert.match(pkg.scripts['lint:text'], /textlint/);
  assert.match(pkg.scripts['lint:text'], /src\/content\/reports\/\*\.md/);
  assert.equal(pkg.scripts.prebuild, 'npm run lint:text');
  assert.ok(pkg.devDependencies.textlint);
  assert.ok(pkg.devDependencies['textlint-rule-preset-ja-technical-writing']);
  assert.ok(pkg.devDependencies['@textlint-ja/textlint-rule-preset-ai-writing']);
  assert.ok(config.rules['preset-ja-technical-writing']);
  assert.ok(config.rules['@textlint-ja/preset-ai-writing']);
});

test('両プリセットが不自然な文と長過ぎる文を検出する', () => {
  const input = `これは革命的な技術です。\n地理空間の分析では、${'観測値'.repeat(40)}を用いて結果を比較します。\n`;
  const result = spawnSync(path.join(root, 'node_modules/.bin/textlint'),
    ['--stdin', '--stdin-filename', 'sample.md'], { cwd: root, input, encoding: 'utf8' });
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /@textlint-ja\/ai-writing\/no-ai-hype-expressions/);
  assert.match(result.stdout, /ja-technical-writing\/sentence-length/);
});

test('Wrangler は公開用 Worker にデプロイする', async () => {
  const config = JSON.parse(await read('wrangler.jsonc'));
  assert.equal(config.name, 'geoai-yuiseki-net');
  assert.equal(config.assets.directory, './dist');
  assert.equal(config.workers_dev, true);
});

test('トップは導入文を置かず、研究一覧から始める', async () => {
  const home = await read('src/pages/index.astro');
  const base = await read('src/layouts/Base.astro');
  assert.doesNotMatch(home, /class="intro|地図から、社会の課題を調べる/);
  assert.match(home, /<h1>公開中の研究<\/h1>/);
  assert.equal(home.match(/<h1[ >]/g).length, 1);
  assert.doesNotMatch(home, /hero-figure|hero-graphic|orbit-one|Selected research|Research notes/);
  assert.match(base, /研究一覧/);
  assert.match(base, /prefers-reduced-motion/);
  assert.doesNotMatch(home + base, /GitHub ↗|研究を読む <span|研究を見る <span/);
});

test('公開ページの画像は元の縦横比を保ち、操作要素は操作性を備える', async () => {
  const home = await read('src/pages/index.astro');
  const base = await read('src/layouts/Base.astro');
  const reportPage = await read('src/pages/reports/[slug].astro');
  const bus = await read('src/content/reports/bus-operator-concentration.md');
  const bear = await read('src/content/reports/akita-bear-risk.md');
  assert.match(home, /<img src=\{report\.data\.image\}[^>]+width=\{report\.data\.imageWidth\}[^>]+height=\{report\.data\.imageHeight\}[^>]+loading="lazy"/);
  assert.doesNotMatch(home, /\.card-image\s*\{[^}]*aspect-ratio:\s*16\/9/);
  assert.match(home, /\.card-image img\s*\{[^}]*height:\s*auto/);
  assert.match(reportPage, /\.prose :global\(img\)\s*\{[^}]*height:\s*auto/);
  assert.match(bus, /imageWidth: 960\nimageHeight: 809/);
  assert.match(bear, /imageWidth: 1706\nimageHeight: 2031/);
  assert.match(base, /<meta name="theme-color" content="#f6f7f4"/);
  assert.match(base, /touch-action: manipulation/);
  assert.match(base, /text-wrap: balance/);
});

test('公開記事は選定済みの三件だけで、出典と限界を持つ', async () => {
  const entries = [
    'src/content/reports/bus-operator-concentration.md',
    'src/content/reports/akita-bear-risk.md',
    'src/content/reports/taito-traffic-accidents.md',
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
  const home = await read('dist/index.html');
  const bus = await read('dist/reports/bus-operator-concentration/index.html');
  const bear = await read('dist/reports/akita-bear-risk/index.html');
  assert.doesNotMatch(home, /<figure class="hero-figure"/);
  assert.match(home, /akita-risk-map\.png"[^>]+width="1706" height="2031" loading="lazy"/);
  assert.match(bus, /class="katex/);
  assert.match(bear, /class="mermaid"/);
  assert.match(bus, /bus-operator-share\.png"[^>]+width="960" height="809" loading="lazy"/);
  assert.match(bear, /akita-risk-map\.png"[^>]+width="1706" height="2031" loading="lazy"/);
  assert.doesNotMatch(bus + bear, /href="\/GeoAI-master-skills\//);
  await stat(path.join(root, 'dist/images/bus-operator-share.png'));
  await stat(path.join(root, 'dist/images/akita-risk-map.png'));
  const taito = await read('dist/reports/taito-traffic-accidents/index.html');
  assert.match(taito, /taito-accident-hotspots\.png"[^>]+width="2154" height="1071" loading="lazy"/);
  await stat(path.join(root, 'dist/images/taito-accident-hotspots.png'));
  await stat(path.join(root, 'dist/favicon.svg'));
});

test('サイト名は「yuiseki の GeoAI 研究所」で、ページタイトルにも付く', async () => {
  const base = await read('src/layouts/Base.astro');
  const home = await read('src/pages/index.astro');
  assert.match(base, /const siteName = 'yuiseki の GeoAI 研究所';/);
  assert.match(base, /<title>\{title \? `\$\{title\} · \$\{siteName\}` : siteName\}<\/title>/);
  assert.doesNotMatch(base, /GeoAI Research/);
  assert.match(home, /<Base description=/);
});
