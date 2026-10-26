# Fetch only coordinates and geotag fields of the pinned geotagged Wikipedia shards (no article text).
import duckdb
c=duckdb.connect(); c.sql('load httpfs')
B='https://huggingface.co/datasets/yuiseki/wikipedia-geotagged/resolve/24e53f69ef27eb099801ecef1bcca501fcd44a07/'
files=[B+f'20260901.en/train-0000{i}-of-00005.parquet' for i in range(5)]+[B+f'20260901.ja/train-0000{i}-of-00002.parquet' for i in range(2)]
print(c.sql(f"describe select * from '{files[0]}'").fetchall())
c.sql(f"""copy (select filename, id, qid, lat, lon, gt_type, gt_globe, gt_primary, gt_country from read_parquet({files}, filename=true)) to 'data/wiki_coords.parquet'""")
print(c.sql("select regexp_extract(filename,'(\\d{8}\\.\\w\\w)',1) l, count(*), count(distinct id), count(lat) from 'data/wiki_coords.parquet' group by 1").fetchall())
