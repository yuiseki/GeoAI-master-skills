# 計画: 範囲の端で止まった連鎖を先まで追い、指定されていない候補を空中写真で確かめる

流す前に書く。流した後に書き直さない。直すなら末尾の「計画の変更」に足す。

## 問いと使い道

- 問い 1 (範囲を広げる): `tameike-cascade-breach` の連鎖の多くは「流れが範囲の外へ出た」で止まり、数は下限だった (2 段以上で人口のある連鎖のうち、香川 24 / 30、福山 22 / 33、淡路 106 / 149)。流れの計算の範囲を広げると、連鎖の数と長さ、指定されていない初めの池の数はどう変わるか。
- 問い 2 (目で確かめる): 指定されていない連鎖の初めの池のうち、人口の多い池は、空中写真と地図で見て、池があり、流れの線の近くに家があるか。
- 使い道: 点検の候補の一覧を、範囲の端の影響を除いた数にし、上位の候補が写真の上でも妥当かを示す。
- 問いの種類: 構造 (仮定のもとでの数え直し) と、目視による確かめ。

## 方法

`tameike-cascade-breach` の判定のしかた (決壊の式、余水吐の能力、余裕高、曝露) と値は全て同じにする。変えるのは次の 2 つだけ。

- 流れの計算の範囲: 元の範囲の四方に 0.04 度足す (香川 133.74〜133.98、34.09〜34.31、福山 133.16〜133.40、34.38〜34.60、淡路 134.74〜134.98、34.36〜34.58)。DEM5A、台帳、WorldPop は広げた範囲で読む。
- 初めの池: 元の範囲の中に台帳の点がある池だけ (元と同じ池の集まり)。あふれる池は広げた範囲のどこでもよい。

あわせて、連鎖の止まった所が計算の範囲の端 (格子の縁) かどうかを記録する。2 段以上の連鎖の流れの線を GeoJSON に書く。

指定の照合は `tameike-cascade-designation` と同じ 4 つの鍵で、香川県の一覧は全ての市町の PDF を使う。一覧の無い県 (徳島県、岡山県) の池は「不明」とする。

## 主張の地図

| claim_id | 主張 | 効く判断 | 区画 |
|---|---|---|---|
| C0 | 広げた計算は、元の計算を範囲の中で再現している | 先へ進むか | B0 |
| C1 | 範囲を広げると、2 段以上で人口のある連鎖の数は元以上になり、計算の範囲の端で止まる連鎖は少なくなる | 下限の数をどこまで直せたか | B1 |
| C2 | 広げても、指定されていない連鎖の初めの池がある (範囲ごとの数) | 候補の一覧を差し替えるか | B2 |
| C3 | 上位の候補は、空中写真と地図の上でも、池があり、流れの線の近くに建物がある | 候補の一覧を点検に渡せるか | B3 |

## 区画

### B0: 再現 (sanity)

- claim tested: C0
- mode: confirmatory
- data / analysis unit: 元の範囲の初めの池 1 つ
- observable quantity: 元の計算で「範囲の外へ出た」以外の理由で止まった初めの池のうち、あふれる池の並び (台帳の行で比べる) が元と同じものの割合
- comparator / control: `tameike-cascade-breach` の主の設定の出力
- evaluation population / split principle: 3 つの範囲の、該当する全ての初めの池
- primary metric: 範囲ごとの、同じ割合
- uncertainty: なし
- planned settings: 上の方法
- decision rule: 3 範囲とも 95% 以上なら先へ進む。下回るなら、違う池を 10 件見て原因を書き、止める
- failure interpretation: 範囲の端の扱い (窪地の埋め方、水面の穴の判定) が中の結果まで変えている
- alternative explanation being tested: 計算の範囲の端の影響が中まで届く
- falsification / robustness: なし
- priority / run order: sanity、順番 1

### B1: 広げた連鎖の数 (decisive)

- claim tested: C1
- mode: confirmatory
- data / analysis unit: 元の範囲の初めの池 1 つ
- observable quantity: 2 段以上で流れの 100 m 以内に 1 人以上の連鎖の数、最も長い連鎖、計算の範囲の端で止まった連鎖の数、13 通りの変え方の幅 (`tameike-cascade-breach` と同じ変え方)
- comparator / control: `tameike-cascade-breach` の主の設定
- evaluation population / split principle: 元の範囲の全ての初めの池
- primary metric: 範囲ごとの、2 段以上で人口のある連鎖の数
- uncertainty: なし (全件)
- planned settings: 上の方法
- decision rule: 数が元以上なら支持。端で止まった連鎖が、2 段以上で人口のある連鎖の 10% を超えて残る範囲は「まだ下限」と書く
- failure interpretation: 元より少ない範囲は、端の扱いが連鎖の判定を変えている。B0 と合わせて原因を書く
- alternative explanation being tested: 範囲の端による打ち切り
- falsification / robustness: 13 通りの変え方
- priority / run order: decisive、順番 2

### B2: 指定されていない初めの池 (decisive)

- claim tested: C2
- mode: confirmatory
- data / analysis unit: B1 の 2 段以上で人口のある連鎖の初めの池
- observable quantity: 指定ありでない初めの池の数と、そのうち人口 100 人以上の数。指定を多めに数える照合での数
- comparator / control: `tameike-cascade-designation` の数 (24、10、70)
- evaluation population / split principle: B1 と同じ
- primary metric: 範囲ごとの、指定ありでない初めの池の数
- uncertainty: なし
- planned settings: `tameike-cascade-designation` の照合
- decision rule: 1 つ以上ある範囲は候補の一覧を出す。多めに数えても残る数を下限として書く
- failure interpretation: 0 なら候補なし
- alternative explanation being tested: 照合の取りこぼし (多めに数える照合)
- falsification / robustness: 多めに数える照合
- priority / run order: decisive、順番 3

### B3: 空中写真と地図での確かめ (exploratory)

- claim tested: C3
- mode: exploratory (判定は目視で、手で書く。再現できる計算ではない)
- data / analysis unit: B2 の候補のうち、範囲ごとに連鎖の人口の多い順に 3 つ (計 9)
- observable quantity: 地理院の空中写真 (seamlessphoto、z17) と標準地図に、初めの池、あふれる池、流れの線、100 m の帯を重ねた図での、次の 3 つ
  - (a) 池: 初めの池とあふれる池が、水面か池の形で写っているか (全て、一部、写っていない)
  - (b) 建物: 流れの線の 100 m の帯の中に建物が見えるか (無い、1〜9 棟ほど、10 棟以上)
  - (c) 流れ: 線が谷筋や川に沿っているか、平地の田や水路の地域を横切るか (谷筋、平地、混ざる)
- comparator / control: なし
- evaluation population / split principle: 上の 9 つ
- primary metric: (a) が「全て」で (b) が「1〜9 棟ほど」以上の候補の数
- uncertainty: なし
- planned settings: 上の図
- decision rule: なし (記述)。判定は `outputs/visual_verdicts.csv` に手で書き、手で書いたことを README に書く
- failure interpretation: (a) が「写っていない」池は、台帳の池が廃止されたか、座標がずれている
- alternative explanation being tested: WorldPop の人口が家の無い所に置かれている。台帳の池が今は無い
- falsification / robustness: なし
- priority / run order: exploratory、順番 4

## 流す順

| 順 | 段 | 区画 | 先へ進む条件 | 飛ばすなら理由 |
|---|---|---|---|---|
| 1 | sanity | B0 | 3 範囲とも 95% 以上 | |
| 2 | decisive | B1 | 結果によらず次へ | |
| 3 | decisive | B2 | 結果によらず次へ | |
| 4 | exploratory | B3 | | |

## 仮定

- `tameike-cascade-breach` と `tameike-cascade-designation` の仮定は全てそのまま
- 0.04 度 (約 4 km) 広げれば、元の範囲から出た連鎖の多くは止まるまで追える (B1 で端で止まる数を数えて確かめる)
- 広げた範囲の雨は、元の範囲の観測所の値を使う

## 判断の規則

| claim_id | 区画 | 規則 | 根拠 |
|---|---|---|---|
| C0 | B0 | 3 範囲とも 95% 以上 | 範囲の端の扱いが中を変えていないことの確かめ |
| C1 | B1 | 元以上なら支持、端で止まる連鎖が 10% を超えたら「まだ下限」 | 打ち切りが残っているかを書くため |
| C2 | B2 | 1 つ以上で候補の一覧を出す | 使い道が点検の候補 |
| C3 | B3 | なし (記述) | 目視の判定は数えるだけにする |

## 計画の変更

| 日付 | 変更 | 理由 | 結果を見た後か |
|---|---|---|---|
