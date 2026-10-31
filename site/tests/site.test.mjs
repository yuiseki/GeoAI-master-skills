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
  assert.match(base, /<meta name="theme-color" content="#061a38"/);
  assert.match(base, /touch-action: manipulation/);
  assert.match(base, /text-wrap: balance/);
});

test('公開記事は選定済みの五件だけで、出典と限界を持つ', async () => {
  const entries = [
    'src/content/reports/bus-operator-concentration.md',
    'src/content/reports/akita-bear-risk.md',
    'src/content/reports/taito-traffic-accidents.md',
    'src/content/reports/tokyo23-daytime-evac-stress.md',
    'src/content/reports/tokyo23-flood-record-vs-a31a.md',
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
  assert.match(base, /const pageTitle = title \? `\$\{title\} · \$\{siteName\}` : siteName;/);
  assert.match(base, /<title>\{pageTitle\}<\/title>/);
  assert.doesNotMatch(base, /GeoAI Research/);
  assert.match(home, /<Base description=/);
});

test('記事のタイトルはやったことを伝え、冒頭で問いとわかったことを示す', async () => {
  const titles = {
    'akita-bear-risk.md': 'オープンデータに基づいた熊出没予測モデルの構築とその限界の調査',
    'taito-traffic-accidents.md': '東京都・台東区の交通事故事例の多角的分析',
    'bus-operator-concentration.md': '高齢化地域におけるバス事業者集中リスクの調査',
    'tokyo23-daytime-evac-stress.md': '東京23区の平日昼間人口から見た避難所の潜在的逼迫の分析',
    'tokyo23-flood-record-vs-a31a.md': '東京23区の浸水実績から学習した予測モデルと洪水浸水想定区域 \\(A31a\\) の比較',
  };
  for (const [file, title] of Object.entries(titles)) {
    const markdown = await read(`src/content/reports/${file}`);
    assert.match(markdown, new RegExp(`^title: ${title}$`, 'm'), file);
    const headings = [...markdown.matchAll(/^## (.+)$/gm)].map((m) => m[1]);
    assert.deepEqual(headings.slice(0, 2), ['問いと取り組んだこと', 'わかったこと'], file);
    assert.ok(headings.includes('限界'), file);
  }
});

test('記事の図は公開フォルダーにあり、幅と高さが実画像と一致する', async () => {
  for (const file of await readdir(path.join(root, 'src/content/reports'))) {
    const markdown = await read(`src/content/reports/${file}`);
    const images = [...markdown.matchAll(/<img src="(\/images\/[^"]+\.png)"[^>]*width="(\d+)" height="(\d+)"/g)];
    assert.ok(images.length > 0, file);
    for (const [, src, width, height] of images) {
      const png = await readFile(path.join(root, 'public', src));
      assert.deepEqual([png.readUInt32BE(16), png.readUInt32BE(20)], [Number(width), Number(height)], `${file} ${src}`);
    }
  }
});

test('クマの記事は評価指標とモデルを専門用語で呼ぶ', async () => {
  const bear = await read('src/content/reports/akita-bear-risk.md');
  assert.match(bear, /上位5%での再現率 \(capture@5%\)/);
  assert.match(bear, /予測モデル `B_env`/);
  assert.doesNotMatch(bear, /当たり|場所の予測|環境だけの地図/);
});

test('バスと台東区の記事は定義した用語で書く', async () => {
  const bus = await read('src/content/reports/bus-operator-concentration.md');
  const taito = await read('src/content/reports/taito-traffic-accidents.md');
  assert.match(bus, /単一事業者メッシュと呼びます/);
  assert.match(bus, /## 定義と感度分析/);
  assert.doesNotMatch(bus, /読み方|停留所圏|追試|元の報告|既存の報告/);
  assert.match(taito, /### 用語の定義/);
  assert.match(taito, /## 定義と感度分析/);
  assert.doesNotMatch(taito, /読み方|過失の重い側が|狭い読み|広い読み|若い \(/);
});

test('記事ごとの OGP 画像を 1200x630 で生成し、メタタグから絶対 URL で参照する', async () => {
  const pngSize = async (file) => {
    const png = await readFile(path.join(root, file));
    return [png.readUInt32BE(16), png.readUInt32BE(20)];
  };
  const ids = (await readdir(path.join(root, 'src/content/reports'))).map((f) => f.replace(/\.md$/, ''));
  for (const id of ids) {
    assert.deepEqual(await pngSize(`dist/ogp/${id}.png`), [1200, 630], id);
    const html = await read(`dist/reports/${id}/index.html`);
    assert.match(html, new RegExp(`<meta property="og:image" content="https://geoai\\.yuiseki\\.net/ogp/${id}\\.png"`), id);
    assert.match(html, /<meta property="og:type" content="article"/, id);
    assert.match(html, new RegExp(`<meta property="og:url" content="https://geoai\\.yuiseki\\.net/reports/${id}/"`), id);
  }
  assert.deepEqual(await pngSize('dist/ogp/default.png'), [1200, 630]);
  const home = await read('dist/index.html');
  assert.match(home, /<meta property="og:image" content="https:\/\/geoai\.yuiseki\.net\/ogp\/default\.png"/);
  assert.match(home, /<meta property="og:site_name" content="yuiseki の GeoAI 研究所"/);
  assert.match(home, /<meta name="twitter:card" content="summary_large_image"/);
});

test('ファビコンは 32x32 のドット絵で、整数倍に拡大して使う', async () => {
  const pngSize = async (file) => {
    const png = await readFile(path.join(root, file));
    return [png.readUInt32BE(16), png.readUInt32BE(20)];
  };
  const svg = await read('public/favicon.svg');
  assert.match(svg, /viewBox="0 0 32 32"/);
  assert.match(svg, /shape-rendering="crispEdges"/);
  assert.deepEqual(await pngSize('public/favicon-32.png'), [32, 32]);
  assert.deepEqual(await pngSize('public/apple-touch-icon.png'), [180, 180]);
  const base = await read('src/layouts/Base.astro');
  assert.match(base, /<link rel="icon" type="image\/svg\+xml" href="\/favicon\.svg"/);
  assert.match(base, /<link rel="apple-touch-icon" href="\/apple-touch-icon\.png"/);
});

test('アクセントカラーはファビコンの GeoAI の文字のシアンにそろえる', async () => {
  const base = await read('src/layouts/Base.astro');
  const ogp = await read('src/lib/ogp.ts');
  const favicon = await read('scripts/make-favicon.py');
  assert.match(favicon, /TEXT, OUTLINE = \(150, 240, 232, 255\), \(6, 26, 56, 255\)/);
  assert.match(base, /--cyan: #96f0e8;/);
  assert.match(base, /--navy: #061a38;/);
  assert.match(base, /--accent: #066b62;/);
  for (const hex of ['#96f0e8', '#061a38', '#066b62']) assert.ok(ogp.includes(hex), hex);
  const sources = [base, ogp, await read('src/pages/index.astro'), await read('src/pages/reports/[slug].astro')].join('\n');
  assert.doesNotMatch(sources, /--green|--orange|#16584f|#9d412c|#b45e35|#104b42/);
});

test('記事にトピックや地域のラベルを付けない', async () => {
  const sources = [
    await read('src/content.config.ts'), await read('src/pages/index.astro'), await read('src/pages/reports/[slug].astro'),
    await read('src/pages/ogp/[slug].png.ts'), await read('src/lib/ogp.ts'),
  ].join('\n');
  assert.doesNotMatch(sources, /topic|kicker|labels|card-meta|report-meta/);
  for (const file of await readdir(path.join(root, 'src/content/reports'))) {
    assert.doesNotMatch(await read(`src/content/reports/${file}`), /^(topic|kicker):/m, file);
  }
});

test('トップページは公開日時の新しい記事から並べる', async () => {
  const published = {};
  for (const file of await readdir(path.join(root, 'src/content/reports'))) {
    const match = (await read(`src/content/reports/${file}`)).match(/^published: (.+)$/m);
    assert.ok(match, file);
    published[file.replace(/\.md$/, '')] = new Date(match[1]).getTime();
  }
  const expected = Object.keys(published).sort((a, b) => published[b] - published[a] || a.localeCompare(b));
  const home = await read('dist/index.html');
  // The masonry columns change the DOM order, so read each card's `order`, which the one-column layout uses.
  const cards = [...home.matchAll(/<article class="report-card"[^>]*style="order: ?(\d+);?"[\s\S]*?href="\/reports\/([^/"]+)\/"/g)];
  assert.equal(cards.length, expected.length);
  assert.deepEqual(cards.sort((a, b) => a[1] - b[1]).map((m) => m[2]), expected);
});

test('トップページは2列のメイソンリーで、1列のときは新しい順に戻す', async () => {
  const home = await read('dist/index.html');
  assert.equal(home.match(/class="masonry-column"/g).length, 2);
  const source = await read('src/pages/index.astro');
  assert.match(source, /\.masonry-column \{ display: contents; \}/);
  assert.match(source, /<img src=\{report\.data\.image\}/);
});

test('レポートで使ったデータセットのカードを /datasets/{id}/ に置き、相互にリンクする', async () => {
  const reports = await readdir(path.join(root, 'src/content/reports'));
  const used = new Set();
  for (const file of reports) {
    const id = file.replace(/\.md$/, '');
    const markdown = await read(`src/content/reports/${file}`);
    const block = markdown.match(/^datasets:\n((?: {2}- .+\n)+)/m);
    assert.ok(block, `${file} lists its datasets`);
    const datasets = [...block[1].matchAll(/- (.+)/g)].map((m) => m[1].trim());
    const reportHtml = await read(`dist/reports/${id}/index.html`);
    for (const dataset of datasets) {
      used.add(dataset);
      assert.match(reportHtml, new RegExp(`href="/datasets/${dataset}/"`), `${id} -> ${dataset}`);
      const datasetHtml = await read(`dist/datasets/${dataset}/index.html`);
      assert.match(datasetHtml, new RegExp(`href="/reports/${id}/"`), `${dataset} -> ${id}`);
      assert.match(datasetHtml, /ライセンス/);
    }
  }
  const built = (await readdir(path.join(root, 'dist/datasets'), { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name);
  assert.deepEqual(built.sort(), [...used].sort(), 'only datasets used by a report get a page');
  // Links between cards point at the site when the target is published, otherwise at GitHub.
  const flood = await read('dist/datasets/tokyo-flood-record-jp/index.html');
  assert.match(flood, /href="\/datasets\/ksj-a31a-flood-tokyo23\/"/);
  assert.doesNotMatch(flood, /href="(?!https:\/\/)[^"]*\.md"/);
  assert.match(flood, /href="https:\/\/github\.com\/yuiseki\/GeoAI-master-skills\/blob\/main\/\.agents\/skills\/dataset-discovery\/references\/huggingface\/yuiseki\/tokyo-flood-record-jp\.md"/);
});
