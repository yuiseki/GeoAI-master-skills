import { readFileSync } from 'node:fs';
import path from 'node:path';
import { Resvg } from '@resvg/resvg-js';
import { loadDefaultJapaneseParser } from 'budoux';
import satori from 'satori';

export const OGP_WIDTH = 1200;
export const OGP_HEIGHT = 630;
export const SITE_NAME = 'yuiseki の GeoAI 研究所';

const colors = { ink: '#1d302f', muted: '#53615e', line: '#cbd3cf', paper: '#f6f7f4', green: '#16584f', accent: '#9d412c' };
const parser = loadDefaultJapaneseParser();

let fonts: { serif: ArrayBuffer; sans: ArrayBuffer } | undefined;

function readFont(name: string): ArrayBuffer {
  const buf = readFileSync(path.resolve(process.cwd(), 'src/assets/fonts', name));
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer;
}

function loadFonts() {
  fonts ??= { serif: readFont('NotoSerifJP-SemiBold.otf'), sans: readFont('NotoSansJP-Bold.otf') };
  return fonts;
}

/**
 * Split a title into budoux phrases. Noto CJK has no glyph for U+200B, so instead of
 * joining phrases with zero-width spaces each phrase becomes its own flex item.
 */
export function phrases(text: string): string[] {
  return parser.parse(text);
}

function titleSize(title: string): number {
  if (title.length <= 20) return 68;
  if (title.length <= 30) return 60;
  return 52;
}

type Node = { type: string; props: Record<string, unknown> };
const h = (type: string, style: Record<string, unknown>, children?: unknown): Node => ({ type, props: { style, children } });

export interface OgpContent {
  title: string;
  /** Small labels above the title, such as the topic and the area. */
  labels?: string[];
}

export async function renderOgpPng({ title, labels = [] }: OgpContent): Promise<Buffer> {
  const { serif, sans } = loadFonts();
  const tree = h('div', { width: '100%', height: '100%', display: 'flex', background: colors.paper }, [
    h('div', { width: 16, height: '100%', background: colors.green }),
    h('div', { flex: 1, display: 'flex', flexDirection: 'column', padding: '64px 72px 52px 64px' }, [
      h('div', { display: 'flex', gap: 28, fontFamily: 'Noto Sans JP', fontSize: 26, color: colors.accent },
        labels.map((label, i) => h('div', { color: i === 0 ? colors.accent : colors.muted }, label))),
      h('div', { flex: 1, display: 'flex', alignItems: 'center' },
        h('div', {
          display: 'flex', flexWrap: 'wrap', fontFamily: 'Noto Serif JP', fontSize: titleSize(title),
          lineHeight: 1.42, color: colors.ink, letterSpacing: '-0.02em',
        }, phrases(title).map((phrase) => h('div', { whiteSpace: 'pre' }, phrase)))),
      h('div', {
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
        borderTop: `2px solid ${colors.line}`, paddingTop: 24, fontFamily: 'Noto Sans JP',
      }, [
        h('div', { fontSize: 30, color: colors.ink }, SITE_NAME),
        h('div', { fontSize: 22, color: colors.muted }, 'geoai.yuiseki.net'),
      ]),
    ]),
  ]);

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
  return new Resvg(svg, { font: { loadSystemFonts: false } }).render().asPng();
}
