# 日本語の文字を図に描く

matplotlib の既定のフォント (DejaVu Sans) には、漢字も仮名も無い。日本語の題や区の名前を描くと、matplotlib は止まらずに警告を出し、文字のところが空の四角 (豆腐) になった図を保存する。警告は大量のログに埋もれやすく、図だけを見る人は気づくまで時間がかかる。描く前に、フォントがあるか、図の全ての文字をそのフォントが描けるかを確かめる。

## 測ったこと (2026-10-17)

| 環境 | 結果 |
|---|---|
| eval の Docker イメージ (Codex 用と OpenCode 用、python:3.12-slim-bookworm が土台) | matplotlib も日本語のフォントも入っていない。エージェントは matplotlib を pip や uv で入れる。root ではないので、apt でフォントは入れられない |
| 同じイメージに matplotlib 3.11.2 だけを入れて、日本語の題で保存 | `Glyph 26481 (\N{CJK UNIFIED IDEOGRAPH-6771}) missing from font(s) DejaVu Sans.` の警告が出て、図はそのまま保存された (終了コードは 0) |
| さらに matplotlib-fontja 1.1.0 を入れて、`import matplotlib_fontja` | `font.family` が IPAexGothic になり、警告は 0 件。マイナス記号 (U+2212) も描けた |
| GeoAI の作業の母艦 (Ubuntu) | Noto Sans CJK JP (fonts-noto-cjk、TTC) がある |

matplotlib-fontja は、IPAex ゴシック (`ipaexg.ttf`) を同梱し、import すると登録して既定のフォントにする。フォントの使用許諾は IPA フォントライセンス v1.0 (同梱の `IPA_Font_License_Agreement_v1.0.txt`)。フォントで描いた図 (PNG) を成果物にするのは問題ないが、フォントのファイルそのものを配るなら、許諾の条件を確かめる。

## `scripts/cjk_font.py`

```sh
python3 scripts/cjk_font.py "図に使う全ての文字"              # 使うフォントの名前を出す。無ければ終了コード 1
python3 scripts/cjk_font.py --font "IPAexGothic" "東京"       # フォントを指定する
```

```python
from cjk_font import use_cjk_font
name = use_cjk_font("23 区の芝生の面積 (m²) 人口 1 人あたり −0.5")
```

- 入っているフォントから、Noto Sans CJK JP、Noto Sans JP、Source Han Sans JP、IPAexGothic、IPAGothic、Hiragino Sans、Yu Gothic、TakaoGothic の順に最初のものを選ぶ。どれも無ければ matplotlib-fontja を import してみる。それも無ければ、入れ方を書いて止まる。
- 選んだフォントの文字の表 (cmap) に、渡した文字が全てあるかを確かめ、無い文字を挙げて止まる。日本語のフォントでも、記号 (², ℃, ㎡) や旧字体が無いことがある。目盛りや凡例の文字も渡す。
- マイナス記号 (U+2212) が無いフォントなら、`axes.unicode_minus` を切って、目盛りの負の数をハイフンで描く。
- テストは `uvx --with matplotlib --with pytest pytest scripts/test_cjk_font.py`。日本語のフォントの無い環境では、実際に描くテストを飛ばす。

## 止まったら

1. pip か uv が使えるなら、`matplotlib-fontja` を入れて、もう一度確かめる。
2. 入れられないなら、図の文字を日本語にしない (区の名前をローマ字か区のコードにして、対応表を報告に書く)。
3. 警告を見逃さないために、描く範囲だけ警告を誤りにする方法もある。

   ```python
   import warnings
   with warnings.catch_warnings():
       warnings.filterwarnings("error", message=".*missing from font")
       fig.savefig("out.png")
   ```
