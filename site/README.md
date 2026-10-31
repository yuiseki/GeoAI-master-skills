# yuiseki の GeoAI 研究所 公開サイト

`projects/` は分析原本のまま残し、`site/src/content/reports/` に置いた公開用の編集済み記事だけをサイトに載せる。図も `site/public/images/` に選んで置く。`docs/` はリポジトリの入門・用語集であり、サイトの公開元ではない。

## ローカル

```sh
cd site
npm ci
npm run build
npm run check
npm run lint:text
npm test
npm run dev
```

Astro の Markdown は Unified を使う。数式には `remark-math` と `rehype-katex` を使う。文中の `$...$` と fenced `math` を描く。`astro-mermaid` は fenced `mermaid` をブラウザーで描く。JavaScript が無効な環境では Mermaid 図が表示されない。PNGは公開を選んだ図だけをコピーしたもの。

`npm run lint:text` は公開記事の Markdown と、この README を検査する。[技術文書向け](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing)と[AI 文体向け](https://github.com/textlint-ja/textlint-rule-preset-ai-writing)の textlint プリセットを適用し、`npm run build` の前にも実行する。Astro テンプレート内の UI 文言は対象外。

## OGP 画像

1200x630 の PNG をビルド時に生成する。記事ごとの画像は `src/pages/ogp/[slug].png.ts`、トップ用の別レイアウトは `src/pages/ogp/default.png.ts` が作る。`src/lib/ogp.ts` が satori で SVG を作り、resvg で PNG にする。タイトルは budoux で文節に分け、文節ごとに折り返す。Noto CJK にはゼロ幅スペースの字形が無いため、文節をゼロ幅スペースでつながず、別々の要素にしている。

フォントは `src/assets/fonts/` に置いた Noto Serif CJK JP SemiBold と Noto Sans CJK JP Bold のサブセット。ライセンスは SIL Open Font License で、本文は `LICENSE-Noto-CJK.txt` にある。サブセットは ASCII、かな、記号、JIS 第1・第2水準の漢字と、記事の front matter の全文字を含む。フォントに無い文字がタイトルに入ると、ビルドは失敗する。その場合は、Debian の `fonts-noto-cjk` を入れた環境でサブセットを作り直す。

```sh
cd site
uv run --no-project --with fonttools python3 scripts/subset-fonts.py
```

## ファビコン

`scripts/make-favicon.py` が、`public/` の `favicon.svg`、`favicon-32.png`、`apple-touch-icon.png` を生成する。32x32 のドット絵で、青い地球に「GeoAI」をドット文字で載せた。地球は Natural Earth 110m の陸地を、日本を中心に正射図法で描く。陸地のデータはコミットを固定した URL から取得し、sha256 を確かめる。雲は固定した正弦波から作るので、乱数を使わず毎回同じ画像になる。大きいサイズは同じ格子の整数倍の拡大で、OGP 画像にも同じ SVG を使う。

```sh
cd site
uv run --no-project --with shapely --with pillow --with numpy python3 scripts/make-favicon.py
```

OGP 画像の左下には、`src/assets/ogp/avatar.jpg` のアバターを置く。

## 公開先

Cloudflare Workers の静的アセットとして `site/dist/` を配信する。`astro.config.mjs` の `site` は `https://geoai.yuiseki.net`、`base` は既定の `/`。`wrangler.jsonc` は Custom Domain と `workers.dev` を宣言している。

ブランチに push すると、Cloudflare 側でビルドとデプロイが走る。このリポジトリにデプロイ用の GitHub Actions は無い。`npx wrangler deploy` を手で実行する必要はない。反映後は、公開ページの `<title>` や見出しを見て確かめる。

公開記事を増やすときは、元の `projects/**/report.md` を無条件に取り込まず、編集した Markdown と必要な図だけを追加し、原本への `source` と限界を必ず書く。
カード用の図には、実画像のピクセル寸法を `imageWidth` と `imageHeight` に記録する。
