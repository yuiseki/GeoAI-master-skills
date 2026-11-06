# 計画: 連鎖の上流にある池は、防災重点農業用ため池に指定されているか

流す前に書く。流した後に書き直さない。直すなら末尾の「計画の変更」に足す。

## 問いと使い道

- 問い: `tameike-cascade-breach` の主の設定で、2 つ以上の池を次々にあふれさせ、流れの 100 m 以内に人が住む連鎖の初めの池 (香川 30、福山 33、淡路 149) のうち、防災重点農業用ため池に指定されていない池はいくつあるか。
- 使い道: 指定されていない連鎖の初めの池は、単独の池としての基準では拾われず、組で見ると危ないかもしれない池である。点検の候補の一覧にする。
- 問いの種類: 記述 (突き合わせて数える)。

指定は、防災重点農業用ため池に係る防災工事等の推進に関する特別措置法 (令和 2 年法律第 56 号) 第 4 条第 1 項による。県が公表した一覧を使う。

## データ

| 範囲 | 一覧 | 時点 | 形 |
|---|---|---|---|
| 香川 (まんのう町、綾川町、三豊市、丸亀市、善通寺市、坂出市、琴平町) | 香川県「防災重点農業用ため池一覧表」市町別 PDF (https://www.pref.kagawa.lg.jp/tochikai/about_tameike/low/low.html) | 令和 8 年 5 月 27 日現在 | 名称、所在地 |
| 福山 (福山市、尾道市、府中市) | 広島県「防災工事等推進計画」別表 2 (https://www.pref.hiroshima.lg.jp/soshiki/90/tameike-policy.html) | 令和 8 年 5 月末時点 | データベースのコード番号、名称、所在地、堤高、堤長、総貯水量 |
| 淡路 (淡路市、洲本市) | 兵庫県「特定農業用ため池、特定ため池及び防災重点農業用ため池指定一覧」Excel (https://web.pref.hyogo.lg.jp/nk11/tokuteitameike_bousaijyuutentameike.html) | 令和 7 年 11 月 7 日 | ため池防災支援システムのコード番号、名称、所在地。防災重点の指定日の欄が空でない行を指定とみなす |

原本は `artifacts/_tameike/tameike-cascade-designation/` に置き、コミットしない。台帳は `tameike-cascade-breach` と同じ (`yuiseki/maff-tameike-list-jp-2026-03`、令和 8 年 3 月末時点)。

## 照合のしかた

一覧の 1 行を、台帳の 1 行に対応づける。どちらも文字を NFKC で正規化し、空白を除く。

1. 鍵 1: 市区町村 + 名称 + 所在地の番地 (所在地の最初の数字の並び。漢数字の丁目は数字に直さない、そのまま比べる)。台帳の市区町村は郡名を除いて比べる。
2. 鍵 1 で 1 行に決まらない一覧の行は、鍵 2: 市区町村 + 名称 で、台帳に同名が 1 行だけなら対応づける。
3. それでも決まらない行は「対応づかない」とし、件数を報告する。

`tameike-cascade-breach` のノード (水面の穴 1 つに対応づいた台帳の点の集まり) は、その台帳の行のどれかが指定されていれば「指定あり」とする。

## 主張の地図

| claim_id | 主張 | 効く判断 | 区画 |
|---|---|---|---|
| C0 | 一覧と台帳の照合が十分に取れている | 先へ進むか | B0 |
| C1 | 連鎖の初めの池のうち、指定されていない池がある (範囲ごとの数) | 点検の候補の一覧を出すか | B1 |
| C2 | 指定されていない初めの池の数は、照合の鍵の取り方で大きく変わらない | 数をどこまで言えるか | B2 |

## 区画

### B0: 照合の健全性 (sanity)

- claim tested: C0
- mode: confirmatory
- data / analysis unit: 範囲に入る市町の一覧の行
- observable quantity: 一覧の行のうち、台帳の 1 行に対応づいた割合 (市町ごと、範囲ごと)。対応づいた組の堤高と貯水量の一致 (広島だけ。一覧に値がある)
- comparator / control: なし
- evaluation population / split principle: 範囲に入る市町の一覧の全行
- primary metric: 範囲ごとの対応づいた割合
- uncertainty: なし
- planned settings: 上の「照合のしかた」
- decision rule: 3 つの範囲の全てで 90% 以上なら先へ進む。下回る範囲は、対応づかない行を 20 件見て原因を書き、鍵を直すなら「計画の変更」に足してから流し直す。直せないなら、その範囲の B1 の数は「指定されていない」を多めに数えうる、と書いて進む
- failure interpretation: 照合の取りこぼしは、指定されている池を「指定されていない」と数える向きに効く
- alternative explanation being tested: 名称や所在地の書き方の揺れ
- falsification / robustness: B2
- priority / run order: sanity、順番 1

### B1: 指定されていない連鎖の初めの池 (decisive)

- claim tested: C1
- mode: confirmatory
- data / analysis unit: `tameike-cascade-breach` の主の設定の初めの池 1 つ (1 行)
- observable quantity: 2 段以上で人口 1 人以上の連鎖の初めの池のうち、指定ありでない池の数。あわせて、そのうち人口 100 人以上の数、連鎖であふれる池 (2 段目以降) のうち指定ありでない池の数
- comparator / control: 全ての初めの池 (貯水量 1,000 m³ 以上で堤高のある池) の、指定ありの割合
- evaluation population / split principle: 範囲の全ての初めの池
- primary metric: 範囲ごとの、指定ありでない連鎖の初めの池の数
- uncertainty: 区間は出さない (全件を数える)
- planned settings: 上の照合
- decision rule: 1 つ以上ある範囲では、点検の候補として一覧 (名称、所在地、貯水量、連鎖の池、人口) を出す。0 の範囲では「連鎖の初めの池は全て指定済み」と書く
- failure interpretation: 0 なら、今の指定の基準で、この連鎖の初めの池は既に拾われている
- alternative explanation being tested: 照合の取りこぼし (B0、B2)
- falsification / robustness: B2
- priority / run order: decisive、順番 2

### B2: 照合の鍵の取り方 (robustness)

- claim tested: C2
- mode: confirmatory
- data / analysis unit: B1 と同じ
- observable quantity: B1 の主の指標
- comparator / control: B1 の主の照合
- evaluation population / split principle: B1 と同じ
- primary metric: B1 と同じ
- uncertainty: なし
- planned settings: (a) 鍵 1 だけ、(b) 市区町村 + 名称で、同名の全ての行を指定ありとする (指定を多めに数える側)
- decision rule: (b) でも指定ありでない連鎖の初めの池が残る範囲は、その数を下限として書く
- failure interpretation: (b) で 0 になる範囲は、B1 の数が照合の取り方に依存すると書く
- alternative explanation being tested: 照合の取りこぼし
- falsification / robustness: これ自体が頑健性の区画
- priority / run order: robustness、順番 3

## 流す順

| 順 | 段 | 区画 | 先へ進む条件 | 飛ばすなら理由 |
|---|---|---|---|---|
| 1 | sanity | B0 | 対応づいた割合が 3 範囲とも 90% 以上 (下回るときは上の規則) | |
| 2 | decisive | B1 | 結果によらず次へ | |
| 3 | robustness | B2 | | |

## 仮定

- 県の一覧は、その時点の指定を全て含む
- 台帳 (令和 8 年 3 月末) と一覧 (令和 7 年 11 月〜令和 8 年 5 月) の時点の違いで、指定の増減があっても少ない
- ノードの台帳の行のどれかが指定されていれば、そのノードは指定ありとみなす (同じ水面の池をまとめて扱うため)

## 判断の規則

| claim_id | 区画 | 規則 | 根拠 |
|---|---|---|---|
| C0 | B0 | 3 範囲とも 90% 以上 | 取りこぼしが 1 割を超えると B1 の数が照合の誤りに支配されうる |
| C1 | B1 | 範囲ごとに 1 つ以上なら候補の一覧を出す | 使い道が点検の候補の一覧のため |
| C2 | B2 | (b) でも残る数を下限として書く | 指定を多めに数えても残る池は、照合の誤りで説明できない |

## 計画の変更

| 日付 | 変更 | 理由 | 結果を見た後か |
|---|---|---|---|
