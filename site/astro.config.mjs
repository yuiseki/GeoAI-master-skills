import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import mermaid from 'astro-mermaid';
import rehypeKatex from 'rehype-katex';
import remarkMath from 'remark-math';

export default defineConfig({
  site: 'https://geoai.yuiseki.net',
  output: 'static',
  integrations: [mermaid({ theme: 'neutral', autoTheme: false, enableLog: false })],
  markdown: {
    processor: unified({ remarkPlugins: [remarkMath], rehypePlugins: [rehypeKatex] }),
    syntaxHighlight: { type: 'shiki', excludeLangs: ['math', 'mermaid'] },
  },
});
