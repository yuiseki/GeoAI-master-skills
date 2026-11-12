"""GOW 北行 9th St → Atlantic Av (4616223) の平日の時刻別の速度 (状態 0) の分位。使い道は報告の注意書き。"""
import pandas as pd
d=pd.read_parquet("/work/artifacts/nyc-arterial-reliability/raw/raw_2026-09.parquet")
d["speed"]=pd.to_numeric(d.speed); d["status"]=pd.to_numeric(d.status); d["t"]=pd.to_datetime(d.data_as_of)
g=d[(d.link_id=="4616223")&(d.status==0)&(d.t.dt.day_of_week<5)]
r=g.groupby(g.t.dt.hour).speed.describe()[["count","25%","50%","75%"]].round(1); r.index.name="hour"
r.to_csv("/work/projects/nyc-arterial-reliability/outputs/check_gow_9th_atlantic_hourly_speed.csv"); print(r.to_string())
