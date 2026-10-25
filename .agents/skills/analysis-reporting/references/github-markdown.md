# GitHub で読む報告の Markdown

- [GitHub Flavored Markdown 仕様](https://github.github.com/gfm/): 見出し、表、画像などの基本構文。表は GFM の拡張。
- [GitHub Docs: 数式の記述](https://docs.github.com/ja/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions): インラインは `$...$`、ブロックは `$$...$$` または fenced `math` block。複雑な式は後者を使う。
- [GitHub Docs: ダイアグラムの作成](https://docs.github.com/ja/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams): fenced `mermaid` block を GitHub が描画する。

GFM の仕様と、GitHub による数式・Mermaid のレンダリングは別のもの。報告の本文に使う表現は、本文、GFM の表、GitHub の数式と Mermaid、Markdown 画像として貼る既存の PNG まで。HTML を報告本体にしない。

数式は量の定義、Mermaid は実際に採用した関係、PNG は実測された値や地理的な分布に使う。少数の値の比較は表が適する。本文で十分なら追加しない。数式に用いる記号、実際の設定値、単位、条件を近くに書く。図の説明も、結論を読み取るために必要なものだけ残す。

表の区切り行、fenced block の開始・終了と中身、画像行も、報告の空でない行数に入る。simple の 8 行、standard の 40 行を回避するために式や図に押し込めない。
