// node --test tests/datasets.test.mjs   (run from site/; needs no node_modules)
//
// Tests for src/lib/datasets.mjs: dataset slugs and the remark plugin that points links between data cards at
// this site or at GitHub. datasets.mjs fixes its paths from process.cwd() when it is imported, so each case runs
// in a child node process whose working directory is a site/ folder inside a temporary copy of the repo layout,
// with small synthetic cards.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const lib = pathToFileURL(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src/lib/datasets.mjs')).href;
const BLOB = 'https://github.com/yuiseki/GeoAI-master-skills/blob/main/';
const REFS = '.agents/skills/dataset-discovery/references';

// node:test has no strict expected failure; this passes while the bug is there and fails once it is fixed.
function xfail(name, reason, fn) {
  test(`${name} [xfail: ${reason}]`, () => {
    let passed = false;
    try {
      fn();
      passed = true;
    } catch {
      return;
    }
    if (passed) assert.fail(`XPASS: ${reason}`);
  });
}

const made = [];
test.after(() => made.forEach((root) => rmSync(root, { recursive: true, force: true })));

function repo(cards) {
  const root = mkdtempSync(path.join(tmpdir(), 'datasets-test-'));
  made.push(root);
  mkdirSync(path.join(root, 'site'));
  for (const [rel, text] of Object.entries(cards)) {
    const file = path.join(root, REFS, rel);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, text);
  }
  return root;
}

// Runs `body` (the text of an async function given the module as `m`) in site/ of `root`; returns its JSON result.
function inSite(root, body) {
  const code = `const m = await import(${JSON.stringify(lib)}); const f = async (m) => { ${body} };
    process.stdout.write(JSON.stringify(await f(m)));`;
  const r = spawnSync(process.execPath, ['--input-type=module', '-e', code], { cwd: path.join(root, 'site'), encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

// Applies the plugin to links found in a card at `from` (relative to the references folder, or absolute).
function rewrite(root, from, urls) {
  const tree = { type: 'root', children: [{ type: 'paragraph', children: urls.map((url) => ({ type: 'link', url, children: [] })) }] };
  const file = from === undefined ? 'undefined' : JSON.stringify(path.isAbsolute(from) ? from : path.join(root, REFS, from));
  return inSite(root, `const tree = ${JSON.stringify(tree)};
    m.remarkCardLinks()(tree, { path: ${file} });
    return tree.children[0].children.map((n) => n.url);`);
}

const CARDS = {
  'esa-worldcover.md': '---\nid: esa/worldcover\ntitle: ESA WorldCover\n---\n# ESA WorldCover\n',
  'huggingface/yuiseki/mlit-underpass.md': '---\nid: yuiseki/mlit-underpass\n---\n# アンダーパス\n',
  'gsi-dem-tiles.md': '---\ntitle: published but without an id\n---\n# 標高タイル\n',
  'other.md': '---\nid: someone/other\n---\n# not published\n',
};

test('datasetSlug は yuiseki/ を外し、残りの / を - にする', () => {
  const got = inSite(repo({}), `return ['yuiseki/ksj-p11-bus-stop-jp', 'esa/worldcover', 'a/b/c', 'xyuiseki/foo', 'plain']
    .map(m.datasetSlug);`);
  assert.deepEqual(got, ['ksj-p11-bus-stop-jp', 'esa-worldcover', 'a-b-c', 'xyuiseki-foo', 'plain']);
});

test('リポジトリの位置は作業ディレクトリ site/ の親から決まる', () => {
  const root = repo({});
  const got = inSite(root, 'return [m.REPO, m.CARDS_ROOT];');
  assert.deepEqual(got, [root, path.join(root, REFS)]);
});

test('公開カードの一覧に重複は無い', () => {
  const got = inSite(repo({}), 'return m.PUBLISHED_CARDS;');
  assert.equal(new Set(got).size, got.length);
  assert.ok(got.includes('esa-worldcover') && got.includes('huggingface/yuiseki/mlit-underpass'));
});

test('公開カードへのリンクはサイトのデータセットページへ、見出しの # は残す', () => {
  const root = repo(CARDS);
  const got = rewrite(root, 'esa-worldcover.md', [
    'huggingface/yuiseki/mlit-underpass.md', 'huggingface/yuiseki/mlit-underpass.md#columns',
  ]);
  assert.deepEqual(got, ['/datasets/mlit-underpass/', '/datasets/mlit-underpass/#columns']);
  const back = rewrite(root, 'huggingface/yuiseki/mlit-underpass.md', ['../../esa-worldcover.md']);
  assert.deepEqual(back, ['/datasets/esa-worldcover/']);
});

test('未公開のカード、公開予定でもファイルが無いカード、id の無いカードは GitHub へ', () => {
  const root = repo(CARDS);
  const got = rewrite(root, 'esa-worldcover.md', ['other.md#x', 'worldpop/japan.md', 'gsi-dem-tiles.md', '../../README.md']);
  assert.deepEqual(got, [
    `${BLOB}${REFS}/other.md#x`,
    `${BLOB}${REFS}/worldpop/japan.md`,
    `${BLOB}${REFS}/gsi-dem-tiles.md`,
    `${BLOB}.agents/skills/README.md`,
  ]);
});

test('URL、ページ内リンク、Markdown 以外のリンクはそのまま', () => {
  const root = repo(CARDS);
  const urls = ['https://example.com/a.md', 'mailto:x@example.com', '#local', 'image.png', 'notes.md.bak'];
  assert.deepEqual(rewrite(root, 'esa-worldcover.md', urls), urls);
});

test('カードの外の Markdown や、パスの無いファイルでは何も変えない', () => {
  const root = repo(CARDS);
  assert.deepEqual(rewrite(root, path.join(root, 'site/src/content/reports/r.md'), ['esa-worldcover.md']), ['esa-worldcover.md']);
  assert.deepEqual(rewrite(root, undefined, ['esa-worldcover.md']), ['esa-worldcover.md']);
  // a folder that only starts with the references folder's name is outside it
  assert.deepEqual(rewrite(root, path.join(root, `${REFS}-old/x.md`), ['esa-worldcover.md']), ['esa-worldcover.md']);
});

test('入れ子の子ノードの中のリンクも書き換える', () => {
  const root = repo(CARDS);
  const got = inSite(root, `const tree = { type: 'root', children: [{ type: 'list', children: [{ type: 'listItem',
      children: [{ type: 'link', url: 'esa-worldcover.md', children: [] }] }] }] };
    m.remarkCardLinks()(tree, { path: ${JSON.stringify(path.join(root, REFS, 'other.md'))} });
    return tree.children[0].children[0].children[0].url;`);
  assert.equal(got, '/datasets/esa-worldcover/');
});

test('id はフロントマターの中からだけ読む', () => {
  const root = repo({ ...CARDS, 'gsi-dem-tiles.md': '---\ntitle: no id\n---\n# 標高タイル\n\nid: from-the-body\n' });
  const got = rewrite(root, 'esa-worldcover.md', ['gsi-dem-tiles.md']);
  assert.notEqual(got[0], undefined);
  assert.deepEqual(got, [`${BLOB}${REFS}/gsi-dem-tiles.md`]);
});
