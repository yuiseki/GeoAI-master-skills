# UNHCR Refugee Population Statistics

UNHCR の難民統計。年ごと、出身国と庇護国の組ごとの難民、庇護申請者、UNHCR が支援する国内避難民、無国籍者の数。庇護申請と決定、帰還、第三国定住、帰化、年齢と性別の内訳。
分析では、国の間の流れ (出身国から庇護国へ) のグラフ、国を単位にした目的変数、紛争データとの時間差のある関係に使う。座標は無い。

## どこから読むか

Hugging Face の `yuiseki/unhcr-refugee-stats`。UNHCR の API から取得した日ごとに版が分かれている。

```
hf://datasets/yuiseki/unhcr-refugee-stats/parquet/<version>/<table>.parquet
```

- `<version>` は取得日。2026-10-10 時点で `2026-10-04` だけ。2025 年末の数字 (2026-06-11 公開) を含む。
- UNHCR は年 2 回上書きし、そのたびに過去の年も改訂する。使った版を報告に書く。
- カード: <https://huggingface.co/datasets/yuiseki/unhcr-refugee-stats>

| テーブル | 行数 | 年 | 1 行 |
|---|---:|---|---|
| `population` | 138,893 | 1951〜2025 | 年 × 出身国 × 庇護国の年末の人数 |
| `asylum-applications` | 120,597 | 2000〜2025 | 庇護申請の件数 |
| `asylum-decisions` | 113,929 | 2000〜2025 | 庇護申請への決定の件数 |
| `solutions` | 21,258 | 1959〜2025 | その年の帰還、第三国定住、帰化 |
| `demographics` | 116,781 | 2001〜2025 | 年齢と性別の内訳 |
| `countries` | 232 | | UNHCR の国の一覧 |

```sql
select "Country of asylum", sum("Refugees under UNHCR's mandate") as refugees
from 'hf://datasets/yuiseki/unhcr-refugee-stats/parquet/2026-10-04/population.parquet'
where "Year" = 2025
group by all order by refugees desc limit 10;
```

列名は CSV の見出しのままで、空白と大文字を含む。SQL では二重引用符で書く。

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 単位 | 年 × 出身国 × 庇護国 (国の組) |
| 空間 | 国。座標は無い |
| ライセンス | CC BY 4.0 に UNHCR の Terms of Use for Datasets が加わる。表示の書式と Terms の URL の掲示が要る。UNHCR が承認したように見せない |

## Natural Earth との結合

出身国と庇護国の ISO 3 文字コード (`Country of origin (ISO)`、`Country of asylum (ISO)`) を Natural Earth の `ISO_A3_EH` と結ぶ (`ISO_A3_EH` は一意でないので、natural-earth.md の方法で本体の国の行だけにしてから)。`population` に出てくる 219 種のうち 213 種が一致する (2026-10-10 実測)。一致しないのは:

- `GLP`、`GUF`、`MTQ`: フランスの海外県。Natural Earth の国の面ではフランスに含まれる
- `TIB`: 出身国の欄にだけ現れる `Tibetan`。国ではなく出身の区分
- `UNK`: 不明。ISO の外
- `XXA`: 無国籍。ISO の外

`countries` の `code` は UNHCR 独自のコードで、ISO と衝突する。UNHCR の `AUS` はオーストリア (ISO は `AUT`)、ISO の `AUS` はオーストラリア。結合には `iso` を使い、`code` は使わない。

## 気をつけること

小さな数は丸められている。 5 未満は 5 の倍数に丸められる。どの数の列にも 1〜4 の値は無い。少数の流れを数えるモデルでは、0 と 5 に値が偏る。

`-` は 0 ではない。 数が無いところは NULL。`Other people in need of international protection` は 2018 年より前には存在せず、138,893 行のうち 138,738 行が NULL。

定義が年で変わる。 無国籍の難民は 2017 年 (ロヒンギャ) と 2020 年 (全ての国) から、難民と無国籍の両方に数えられる。両方を足すとその年以降は二重に数える。長い時系列を作る前に UNHCR の方法論のページを読む。

件と人が混ざっている。 庇護申請と決定は `Cases / Persons` が `C` (件) か `P` (人)。分けて合計する。

`IDPs of concern to UNHCR` は国内避難民の全数ではない。 UNHCR が保護や支援をしている人だけ。全数は IDMC のデータで、ここには入っていない。

名前の末尾に空白がある。 `Unknown ` と `Curacao `。名前でなく ISO コードで結ぶ。
