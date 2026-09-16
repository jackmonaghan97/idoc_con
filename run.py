#%%
from shared import import_duckdb, main
from boto3.session import Session
import boto3
import pandas as pd
import json
import os
import duckdb
import pandas as pd

with open("C:\\Users\\jackm\\OneDrive\\Documents\\git_projects\\r2-config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

# grab sensitive creds
ACCESS_KEY = cfg.get("R2_ACCESS_KEY")
SECRET_KEY = cfg.get("R2_SECRET_KEY")
ACCOUNT_ID = cfg.get("R2_ACCOUNT_ID")

# other variables
BUCKET = "portfolio-data"
REGION = "auto"
ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
LOCAL_DIR = "C:\\Users\\jackm\\OneDrive\\Documents\\git_projects\\portfolio_data\\"

os.makedirs(LOCAL_DIR, exist_ok=True)


files = [
    'prison-population-data-sets.html',
    'prison-exit-data-sets.html',
    'prison-admission-data-sets.html'
    ]

for f in files: main(f)
files = [f.split('.')[0].replace('-', '_') for f in files]

# connect
db_path = r"C:\Users\jackm\OneDrive\Documents\duckdb_cli-windows-amd64\my_database.duckdb"
conn = duckdb.connect(db_path)

# grab tables and close connection
results = {tbl: import_duckdb(tbl, conn) for tbl in files}
conn.close()

sess = Session(
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name=REGION)
s3 = sess.client("s3", endpoint_url=ENDPOINT)

uploaded = []
for name, df in results.items():
    local_path = os.path.join(LOCAL_DIR, name + ".csv")
    df.to_csv(local_path, index=False)

    key = f"{name}.csv"
    s3.upload_file(local_path, BUCKET, key, ExtraArgs={"ContentType": "text/csv"})

    head = s3.head_object(Bucket=BUCKET, Key=key)
    uploaded.append({
        "key": key,
        "size": head.get("ContentLength"),
        "etag": head.get("ETag")
    })

 # %%
