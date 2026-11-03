// Data cards for the datasets the published reports use. The cards are read in place from the
// dataset-discovery skill, so the site never holds a copy that drifts from them.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

// Astro runs from site/. import.meta.url would point into the build output once this is bundled.
const SITE = process.cwd();
export const REPO = path.resolve(SITE, '..');
export const CARDS_ROOT = path.join(REPO, '.agents/skills/dataset-discovery/references');
export const GITHUB_BLOB = 'https://github.com/yuiseki/GeoAI-master-skills/blob/main/';

/** Card paths under CARDS_ROOT, without `.md`. Add a card here when a published report starts using it. */
export const PUBLISHED_CARDS = [
  'esa-worldcover',
  'gsi-dem-tiles',
  'worldpop/japan',
  ...[
    'agera5-japan-monthly-temperature-1979-2026',
    'akita-kumadas-wildlife-sighting',
    'akita-vegetation-2024',
    'esa-worldcover-tokyo-2021-100m',
    'estat-boundary-2020',
    'estat-census-mesh-2020',
    'fagus-crenata-masting-jp-2026-06',
    'gifu-bear-sighting',
    'gsi-evacuation-sites-jp',
    'ishikawa-bear-incident',
    'jma-rain-tokyo',
    'jp-admin-2026-09',
    'ksj-a31a-flood-tokyo23',
    'ksj-p11-bus-stop',
    'kyoto-bear-sighting',
    'landsat5-fagus-crenata-sites-jp-2026-10',
    'mlit-1km-fromto-2022-01',
    'mlit-kansui-flood-prone-points-jp-2026-09',
    'mlit-underpass',
    'nagaoka-bear-sighting',
    'npa-traffic-accidents',
    'osm-japan-src-2026-08',
    'osm-tokyo23-src-2026-08',
    'tokyo-flood-record-jp',
  ].map((name) => `huggingface/yuiseki/${name}`),
];

/** `yuiseki/ksj-p11-bus-stop-jp` -> `ksj-p11-bus-stop-jp`, `esa/worldcover` -> `esa-worldcover`. */
export function datasetSlug(id) {
  return id.replace(/^yuiseki\//, '').replaceAll('/', '-');
}

function cardId(file) {
  const match = readFileSync(file, 'utf8').match(/^---\n[\s\S]*?^id: (.+)$/m);
  return match ? match[1].trim() : undefined;
}

const publishedFiles = new Set(PUBLISHED_CARDS.map((card) => path.join(CARDS_ROOT, `${card}.md`)));

/**
 * Remark plugin: inside a card, a relative link to another card points at its page on this site
 * when that card is published, and at the card on GitHub otherwise.
 */
export function remarkCardLinks() {
  return (tree, file) => {
    const from = file.path ? path.resolve(file.path) : '';
    if (!from.startsWith(CARDS_ROOT + path.sep)) return;
    const walk = (node) => {
      if (node.type === 'link' && /^[^:#]+\.md(#.*)?$/.test(node.url)) {
        const [target, hash = ''] = node.url.split('#');
        const resolved = path.resolve(path.dirname(from), target);
        const id = publishedFiles.has(resolved) && existsSync(resolved) ? cardId(resolved) : undefined;
        node.url = id
          ? `/datasets/${datasetSlug(id)}/${hash ? `#${hash}` : ''}`
          : `${GITHUB_BLOB}${path.relative(REPO, resolved)}${hash ? `#${hash}` : ''}`;
      }
      node.children?.forEach(walk);
    };
    walk(tree);
  };
}
