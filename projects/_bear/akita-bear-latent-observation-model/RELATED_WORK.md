# 関連する研究

ユーザーが挙げた候補を 2026-10-31 に Web で確かめた。要約は検索で見た抄録、索引、報道の範囲で、全文を読んで確かめたのは Sun et al. 2019 だけ。確かめられなかったものは「未確認」と書き、内容を補わない。

## この研究の位置 (系譜の交点)

この研究は次の 3 つの系譜の交点にある。

1. 観測系の統合 (integrated model): 1 つの潜在の空間過程に、観測系ごとの検出の過程を重ねる (Sun 2019、Tenan 2017、Tourani 2020)。
2. 機会的な記録の観測の偏り: 熊の目撃や通報は人のいる所でしか起きない (Ditmer 2021、Munteanu 2026、Nakamoto & Fukazawa 2025)。
3. 潜在の状態の時間変化と不完全な検出: 動的な占有モデル (Piédallu et al. 2017、Bled et al. 2013)。

人側の曝露と衝突の結び付き (Puri 2023) は、H を観測の過程にも結果にも置く理由になる。

ユーザーの検索でも、この研究の検索でも、熊側の潜在の状態と人側の潜在の状態を同時に置き、熊だけ、通報だけ、人側だけ、熊 + 通報、変化なしの合成シナリオで「この観測の設計から原因を識別できるか」を実データの前に試す構成の論文は見つかっていない。「初めて」とは主張しない。

## 最優先の 6 本

| 文献 | 確認 | 内容 (抄録、索引の範囲) | この研究との関係 |
|---|---|---|---|
| Ditmer, M. A. et al. Artificial night light helps account for observer bias in citizen science monitoring of an expanding large mammal population. Journal of Animal Ecology (2021 年の号、オンラインは 2020 年 9 月)。doi:10.1111/1365-2656.13338 | 確認 | ミネソタ州のアメリカクロクマの市民の目撃を占有モデルで解析。目撃は人のいる所に偏る。住宅の密度などより、衛星の夜間光が観測の偏りの補正に最も効いた。補正しないと明るい都市の周りに熊が多いと誤って予測する | 人側の proxy を観測の過程の共変量に置く (この研究の c_E、c_K)。夜間光は時系列の人側のデータの候補 |
| Munteanu, C. et al. Political legacies shape bear use of anthropogenic spaces. bioRxiv 2025.11.20.689425 (2025)。データ Zenodo 18244411 (2026)。雑誌版 (KIT の書誌では "Legacies of historical population management shape contemporary bear use of anthropogenic spaces"、Springer、2026 年 8 月) | 確認 (雑誌版の書誌は 1 つの索引だけ) | ルーマニアのヒグマの 1 万件以上の遭遇の通報 (2019〜2024 年) を階層の占有モデルで、生態の過程と検出の過程に分ける。検出は熊と人の両方の活動の型に強く依存する | 通報を生態の過程と検出の過程に分ける点でこの研究に最も近い。ただし観測系は 1 つ |
| Sun, C. C., J. A. Royle, and A. K. Fuller. Incorporating citizen science data in spatially explicit integrated population models. Ecology 100(9): e02777 (2019)。doi:10.1002/ecy.2777 | 確認 (全文) | 熊の活動の中心の潜在の点過程に、計画的な SCR と市民科学の在・不在を重ねる。シミュレーションで、在・不在のデータの地点の数と検出の確率の効果を比べる | 計画的で努力の分かる観測系が機会的な観測系を較正する。この研究にはそれが無い (CONCEPT.md) |
| Tenan, S. et al. Data integration for inference about spatial processes: A model-based approach to test and account for data inconsistency. PLOS ONE 12(10): e0185588 (2017) | 確認 | イタリア・アルプスのヒグマで SCR、テレメトリ、機会的な観測を統合し、データの組合せごとの推定を比べて食い違いを検定し、それを考慮する | 観測系の間の食い違いの検定。この研究の観測系をまたぐ検証と反証 (F1、F2) に対応 |
| Piédallu, B., P.-Y. Quenette, N. Bombillon, A. Gastineau, C. Miquel, and O. Gimenez. Oryx (2017)。doi:10.1017/S0030605317000321 (ピレネーのヒグマの動的な占有モデル) | 確認 (題は索引の範囲で未確認) | 2008〜2014 年の非侵襲の検出・非検出で、局所の定着と消失を持つ動的な占有モデル。利用の有意な減少と、人口密度との負の相関 | 潜在の状態の時間変化を不完全な検出の下で推定する。努力の分かる計画的な調査があるので識別できる |
| Puri, M. et al. Safe space in the woods: Mechanistic spatial models for predicting risks of human-bear conflicts in India. Biotropica 55(2): 504–516 (2023)。doi:10.1111/btp.13204 | 確認 | ナマケグマの占有を痕跡の調査で推定し、住民への聞き取り 675 件で襲撃のリスクを熊の出現と人の曝露からモデル化 | 熊の分布 × 人の曝露 → 衝突の構造。この研究の encounter(B, H) |

## 外側の研究

| 文献 | 確認 | 内容 | 関係 |
|---|---|---|---|
| Tourani, M. et al. Multiple observation processes in spatial capture–recapture models: How much do we gain? Ecology 101(7) (2020)。doi:10.1002/ecy.3030 | 確認 | 個体の識別が不完全な複数の観測系を統合した SCR。検出の確率が低く個体に結び付かない検出が多いときに得が大きい。パキスタン北部のヒグマ | 観測系を足す得の大きさの条件 |
| Bled, F., J. D. Nichols, and R. Altwegg. Dynamic occupancy models for analyzing species' range dynamics across large geographic scales. Ecology and Evolution (2013)。doi:10.1002/ece3.858 | 2013 年の論文は確認。「Bled 2017」は見つからない | 格子のアトラスのデータを、不均一な調査の過程と空間相関を考慮した動的な占有モデルで解析し、分布の変化を調べる | 環境省の分布メッシュのような格子の記録の時期の間の変化。ユーザーの挙げた 2017 年の文献が別にあるかは未確認 |
| Gantchoff 2022 | 未確認 | Gantchoff, Conlee, Belant の「市民科学で大型食肉目の分布を地図にできるか」が Missouri Department of Conservation の文献一覧に「審査中」として載る。2022 年の出版は確認できない | 市民の観測で分布を推定する系譜と考えられるが、内容は未確認 |
| Honda & Kozakai 2026 | 未確認 | 2026 年の論文は見つからない。確認できたのは Honda, T. and C. Kozakai. Mechanisms of human-black bear conflicts in Japan: In preparation for climate change. Science of the Total Environment 739: 140028 (2020) | 2020 年の論文は、食物の不足が人とツキノワグマの衝突を起こす仕組みの整理 |
| Nakamoto, S. and Y. Fukazawa. Bear warning: predicting encounters using temporal, environmental, and demographic features. International Journal of Data Science and Analytics (2025) | 確認 (研究室の地図のページの記載から) | 東北などの熊の遭遇のリスクを時間、環境、人口の特徴で予測する機械学習の地図 | 通報を教師にした予測器で、この研究の M_B、M_H、B_env と同じ側。潜在の状態と観測の過程を分けない |
| 森林総研 2025 | 未確認 | 2025 年の森林総研の発表そのものは見つからない。見つかったのは、森林総研の大西尚樹氏の報道での見解 (出没の主因は個体数の増加と分布域の拡大) と、東北森林管理局の令和 6 年度の発表集の記事 | 原典を確かめるまで引用しない |

## 確かめた出典

- Ditmer et al.: <https://zendy.io/title/10.1111/1365-2656.13338>、<https://datadryad.org/dataset/doi:10.5061/dryad.59zw3r25c>、<https://seas.umich.edu/news/artificial-night-light-helps-account-observer-bias-wildlife-conservation-efforts>
- Munteanu et al.: <https://www.biorxiv.org/content/10.1101/2025.11.20.689425.full.pdf>、<https://zenodo.org/records/18244411>、<https://publikationen.bibliothek.kit.edu/1000196626>
- Tenan et al.: <https://pmc.ncbi.nlm.nih.gov/articles/PMC5626469>
- Piédallu et al.: <https://cambridge.org/core/services/aop-cambridge-core/content/view/S0030605317000321>、<https://www.biorxiv.org/content/10.1101/075895v2.full>
- Puri et al.: <https://www.ncbs.res.in/content/safe-space-woods-mechanistic-spatial-models-predicting-risks-human-bear-conflicts-india>
- Tourani et al.: <https://zendy.io/title/10.1002/ecy.3030>、<https://umimpact.umt.edu/en/publications/multiple-observation-processes-in-spatial-capturerecapture-models/>
- Bled et al.: <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3892356/>
- Gantchoff: <https://research.mdc.mo.gov/sites/default/files/2023-11/blackBearPublications.pdf>
- Honda and Kozakai 2020: <https://pubmed.ncbi.nlm.nih.gov/32758947/>
- Nakamoto and Fukazawa: <https://fukazawa-lab.github.io/japan-bear-map/index_en.html>
- 森林総研の関係者の見解: <https://weathernews.jp/news/202511/050146/>、<https://www.rinya.maff.go.jp/tohoku/sidou/attach/pdf/R6_happyoushuu-1.pdf>
