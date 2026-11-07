# 記録: PEMS-BAY の DCRNN の再現

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | C0 | confirmatory | 準備 | pems-bay.h5 (sha256 64784b76…、2019-01-09 の版)、distances_bay_2017.csv | done | outputs/prepared.csv | - | 試料 52,093、学習 36,465、検証 5,209、試験 10,419。隣接行列の自分以外の辺 2,369。0 の割合 0.000031 |
| R002 | B0、B1 | C0、C3 | confirmatory | M0 過去の平均、M1 最後の値 | 同上 | done | outputs/baselines.csv | - | M0 の MAE 2.4394 (論文 2.88 ± 0.3 の外。作り方を見直す、モデルの判定は止めない)。M1 は 15 分 1.5976、30 分 2.1789、1 時間 3.0483。論文の FC-LSTM (2.05、2.20) を 15 分と 30 分で下回る |
| R003 | B1、B2 | C1、C2 | confirmatory | 時間の試走 (種 99、50 バッチ) | 同上 | done | artifacts の trial/ | - | 50 バッチと 640 試料の検証で K = 2 は 25 秒、K = 0 は 6 秒。1 エポックは K = 2 で約 4 分、K = 0 で約 1 分。試験の点を見る前に予算を固定: エポックの上限を 60 (計画の変更 1)、種 1、K = 2 と K = 0 を GPU 0 で同時に |
| R004 | B1、B2 | C1、C2 | confirmatory | K = 2 と K = 0 を GPU 0 で同時に | 同上 | failed | ~/logs/pems_k2.log, ~/logs/pems_k0.log | - | 1 エポック目に両方とも GPU のメモリ不足 (1 本 2.5〜3 GB、空き 5.6 GB)。常駐のサービスは影響なし。順に流し直す (R005) |
| R005 | B1、B2 | C1、C2 | confirmatory | K = 2、続けて K = 0 (GPU 0、順に) | 同上 | running | outputs/train_k2_s1.csv, outputs/train_k0_s1.csv | - | 予算は R003 と同じ |
