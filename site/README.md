# GeoAI Research 公開サイト

`projects/` は分析原本のまま残し、`site/src/content/reports/` に置いた公開用の編集済み記事だけをサイトに載せる。図も `site/public/images/` に選んで置く。`docs/` はリポジトリの入門・用語集であり、サイトの公開元ではない。

## ローカル

```sh
cd site
npm ci
npm run build
npm run check
npm test
npm run dev
```

Astro の Markdown は Unified を使い、`remark-math` と `rehype-katex` で文中 `$...$` と fenced `math` を描く。`astro-mermaid` は fenced `mermaid` をブラウザーで描く。JavaScript が無効な環境では Mermaid 図が表示されない。PNGは公開を選んだ図だけをコピーしたもの。

## 公開先

Cloudflare Workers の静的アセットとして `site/dist/` を配信する。`astro.config.mjs` の `site` は `https://geoai.yuiseki.net`、`base` は既定の `/`。`wrangler.jsonc` は Custom Domain を宣言しているが、実デプロイ前に `yuiseki.net` のCloudflareゾーン、既存DNSレコード、権限を確認すること。現時点でデプロイは行っていない。

```sh
cd site
npm run build
npx wrangler deploy
```

公開記事を増やすときは、元の `projects/**/report.md` を無条件に取り込まず、編集した Markdown と必要な図だけを追加し、原本への `source` と限界を必ず書く。
