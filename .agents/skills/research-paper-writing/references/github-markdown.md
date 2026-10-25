# GitHub で読む論文の表現

- [GitHub Flavored Markdown 仕様](https://github.github.com/gfm/): 見出し、表、画像リンクなどの基本。
- [GitHub Docs: 数式の記述](https://docs.github.com/ja/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions): インライン `$...$`、ブロック `$$...$$` または fenced `math` block。
- [GitHub Docs: ダイアグラムの作成](https://docs.github.com/ja/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams): fenced `mermaid` block。

GFM の表・画像構文と、GitHub 独自の数式・Mermaid レンダリングは別の仕組み。本文で1〜2文で伝わることに図式を足さない。数式は実際に使った量の定義、Mermaid は実際の関係、PNG は測定値を示す。外部の閲覧者にも画像が見えるよう、project 内の既存 PNG への相対パスを使う。

図は `![図1: 内容](outputs/figure.png)` のように貼り、続けて「図1. 何を、どの単位・期間・設定で示すか。入力と図の来歴は [出力](outputs/figure.json)」のように短く記す。表は直前に「表1. ...」と書いて Markdown table を置ける。番号は読者の参照のためであり、HTML のタグや自動番号には依存しない。数式と表は本文の結果を装飾目的で繰り返さない。
