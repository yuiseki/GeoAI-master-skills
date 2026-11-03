import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import mermaid from 'astro-mermaid';
import rehypeKatex from 'rehype-katex';
import remarkMath from 'remark-math';
import { remarkCardLinks } from './src/lib/datasets.mjs';

export default defineConfig({
  site: 'https://geoai.yuiseki.net',
  output: 'static',
  integrations: [mermaid({ theme: 'neutral', autoTheme: false, enableLog: false })],
  markdown: {
    processor: unified({ remarkPlugins: [remarkMath, remarkCardLinks], rehypePlugins: [rehypeKatex] }),
    syntaxHighlight: { type: 'shiki', excludeLangs: ['math', 'mermaid'] },
  },
});
