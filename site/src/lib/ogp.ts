import { readFileSync } from 'node:fs';
import path from 'node:path';
import { Resvg } from '@resvg/resvg-js';
import { loadDefaultJapaneseParser } from 'budoux';
import satori from 'satori';

export const OGP_WIDTH = 1200;
export const OGP_HEIGHT = 630;
export const SITE_NAME = 'yuiseki の GeoAI 研究所';
export const SITE_TAGLINE = '地理空間オープンデータを駆使した調査レポートと調査手法を公開中';

// Same tokens as the site CSS: the cyan and navy of the favicon's GeoAI lettering.
const colors = { ink: '#13243a', muted: '#4f5f6b', line: '#c8d3d6', paper: '#f5f8f8', navy: '#061a38', cyan: '#96f0e8', accent: '#066b62' };
const parser = loadDefaultJapaneseParser();

let assets: { serif: ArrayBuffer; sans: ArrayBuffer; marble: string; avatar: string } | undefined;

function read(relative: string): Buffer {
  return readFileSync(path.resolve(process.cwd(), relative));
}

function toArrayBuffer(buf: Buffer): ArrayBuffer {
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer;
}

function loadAssets() {
  assets ??= {
    serif: toArrayBuffer(read('src/assets/fonts/NotoSerifJP-SemiBold.otf')),
    sans: toArrayBuffer(read('src/assets/fonts/NotoSansJP-Bold.otf')),
    // The favicon is a 32x32 pixel grid drawn with crispEdges, so it scales without blurring.
    marble: `data:image/svg+xml;base64,${read('public/favicon.svg').toString('base64')}`,
    avatar: `data:image/jpeg;base64,${read('src/assets/ogp/avatar.jpg').toString('base64')}`,
  };
  return assets;
}

/**
 * Split a title into budoux phrases. Noto CJK has no glyph for U+200B, so instead of
 * joining phrases with zero-width spaces each phrase becomes its own flex item.
 */
export function phrases(text: string): string[] {
  // budoux can join words across spaces, and a dataset id such as
  // `(akita-kumadas-wildlife-sighting)` is one phrase. Break after spaces, keep an id whole so it
  // moves to the next line intact, and split it after hyphens only when it cannot fit on a line.
  const pieces = parser
    .parse(text)
    .flatMap((phrase) => phrase.split(/(?<= )/)) // a space is always a break opportunity
    .flatMap((phrase) => (phrase.length > 36 ? phrase.split(/(?<=[-/_])/) : [phrase]));
  // Move a leading space onto the previous piece, where it ends a line invisibly instead of indenting the next.
  return pieces.reduce<string[]>((out, piece) => {
    const lead = piece.match(/^ +/)?.[0] ?? '';
    if (lead && out.length) out[out.length - 1] += lead;
    const rest = piece.slice(lead.length);
    if (rest) out.push(rest);
    return out;
  }, []);
}

function titleSize(title: string): number {
  if (title.length <= 20) return 64;
  if (title.length <= 30) return 56;
  if (title.length <= 42) return 50;
  return 44;
}

type Node = { type: string; props: Record<string, unknown> };
const h = (type: string, style: Record<string, unknown>, children?: unknown, props: Record<string, unknown> = {}): Node =>
  ({ type, props: { style, children, ...props } });
const img = (src: string, size: number, style: Record<string, unknown> = {}) =>
  h('img', { width: size, height: size, ...style }, undefined, { src, width: size, height: size });

function wrapped(text: string, style: Record<string, unknown>): Node {
  return h('div', { display: 'flex', flexWrap: 'wrap', ...style },
    phrases(text).map((phrase) => h('div', { whiteSpace: 'pre' }, phrase)));
}

/** The avatar sits in the lower left of every card. */
function footer(left: string, right: string): Node {
  const { avatar } = loadAssets();
  return h('div', {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    borderTop: `2px solid ${colors.line}`, paddingTop: 22, fontFamily: 'Noto Sans JP',
  }, [
    h('div', { display: 'flex', alignItems: 'center', gap: 18 }, [
      img(avatar, 56, { borderRadius: 28, border: `2px solid ${colors.line}` }),
      h('div', { fontSize: 28, color: colors.ink }, left),
    ]),
    h('div', { fontSize: 22, color: colors.muted }, right),
  ]);
}

function card(body: Node, foot: Node): Node {
  return h('div', { width: '100%', height: '100%', display: 'flex', background: colors.paper }, [
    h('div', { width: 16, height: '100%', background: colors.navy }),
    h('div', { width: 6, height: '100%', background: colors.cyan }),
    h('div', { flex: 1, display: 'flex', flexDirection: 'column', padding: '56px 72px 44px 64px' }, [body, foot]),
  ]);
}

async function toPng(tree: Node): Promise<Uint8Array<ArrayBuffer>> {
  const { serif, sans } = loadAssets();
  const svg = await satori(tree as Parameters<typeof satori>[0], {
    width: OGP_WIDTH,
    height: OGP_HEIGHT,
    fonts: [
      { name: 'Noto Serif JP', data: serif, weight: 600, style: 'normal' },
      { name: 'Noto Sans JP', data: sans, weight: 700, style: 'normal' },
    ],
    // satori asks for extra assets only when the fonts lack a glyph; fail the build instead of drawing tofu.
    loadAdditionalAsset: async (code, segment) => {
      throw new Error(`OGP fonts lack glyphs for ${JSON.stringify(segment)} (${code}); rerun scripts/subset-fonts.py`);
    },
  });
  return new Uint8Array(new Resvg(svg, { font: { loadSystemFonts: false } }).render().asPng());
}

/** A card for one page: the title, an optional line under it, and the marble. */
export async function renderOgpPng({ title, subtitle }: { title: string; subtitle?: string }): Promise<Uint8Array<ArrayBuffer>> {
  const { marble } = loadAssets();
  const heading = wrapped(title, {
    fontFamily: 'Noto Serif JP', fontSize: titleSize(title), lineHeight: 1.42, color: colors.ink, letterSpacing: '-0.02em',
  });
  const body = h('div', { flex: 1, display: 'flex', alignItems: 'center', gap: 48 }, [
    h('div', { flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 22 }, subtitle
      ? [heading, wrapped(subtitle, { fontFamily: 'Noto Sans JP', fontSize: 28, lineHeight: 1.6, color: colors.muted })]
      : [heading]),
    img(marble, 192),
  ]);
  return toPng(card(body, footer(SITE_NAME, 'geoai.yuiseki.net')));
}

/** The home page card: the marble, the site name as h1 and the tagline as h2. */
export async function renderHomeOgpPng(): Promise<Uint8Array<ArrayBuffer>> {
  const { marble } = loadAssets();
  const body = h('div', { flex: 1, display: 'flex', alignItems: 'center', gap: 56 }, [
    img(marble, 288),
    h('div', { flex: 1, display: 'flex', flexDirection: 'column', gap: 26 }, [
      h('div', { fontFamily: 'Noto Serif JP', fontSize: 60, lineHeight: 1.3, color: colors.ink, letterSpacing: '-0.03em', whiteSpace: 'nowrap' }, SITE_NAME),
      wrapped(SITE_TAGLINE, { fontFamily: 'Noto Sans JP', fontSize: 32, lineHeight: 1.6, color: colors.muted }),
    ]),
  ]);
  return toPng(card(body, footer('yuiseki', 'geoai.yuiseki.net')));
}
