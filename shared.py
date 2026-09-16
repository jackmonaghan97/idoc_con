#%%

# import packages
from csv import excel

from bs4 import BeautifulSoup
from datetime import datetime
from duckdb import df
import pandas as pd
import io
import requests
import shutil
import os
import duckdb
from tqdm import tqdm

URL = 'https://idoc.illinois.gov/reportsandstatistics/'
# prison-exit-data-sets.html
# prison-admission-data-sets.html
# prison-population-data-sets.html

NAMES = {
            
    # basic
    'IDOC #'            : 'docnbr',
    'Name'              : 'fullname',
    'Date of Birth'     : 'birthdt',
    'Sex'               : 'sex',
    'Race'              : 'race',
    'Holding Offense'   : 'hofnscd',
    'Admission Type'    : 'admtyp',
    'Sentence Date'     : 'sntdt',
    'Sentencing County' : 'stnccty',
            
    # admissions
    'Reception Center'  : 'recpcntr',
    'Admission Date'    : 'admitdt',

    # population
    'Actual Mandatory Supervised Release (MSR) Date' : 'actmsrdt', 
    'Actual Discharge Date' : 'actdisdt',
    'Discharge Reason' : 'discrsn', 
    'Special Release Reason' :'sperlsrsn',
    'Releasing Institution' : 'relinst',

    # exits
    'Parent Institution' : 'prtinst',
    'Custody Date': 'cstdt'}
TYPES = {
        
    # basic
    'docnbr' : str,
    'fullname' : str,
    'birthdt' : 'datetime64[ns]',
    'sex' : str,
    'race' : str,
    'hofnscd' : str,
    'admtyp' : str,
    'sntdt' : 'datetime64[ns]',
    'stnccty' : str,
            
    # admissions
    'recpcntr' : str,
    'admitdt' : 'datetime64[ns]',

    # population
    'actmsrdt' : 'datetime64[ns]', 
    'actdisdt' : 'datetime64[ns]',
    'discrsn' : str, 
    'sperlsrsn' : str,
    'relinst' : str,

    # exits
    'prtinst' : str,
    'cstdt' : 'datetime64[ns]'}

def fetch_excels(str_type : str) -> None:

    # fetch 
    response = requests.get(URL + str_type)
    html_content = response.content

    # grab all
    soup = BeautifulSoup(html_content, 'html.parser')   # parse
    links = soup.find_all('a', href=True)               # find links

    # select sub-folders that are excels
    return [link['href'] for link in links if link['href'].endswith('.xlsx') or link['href'].endswith('.xls')]
      
def header(_df : pd.DataFrame) -> pd.DataFrame:

    # find column row
    for idoc_c in _df.columns:

        if pd.notna(_df[idoc_c].iloc[5]): break
        else: pass # exit loop when found
        
    # Next we need to find the correct header row. This should be where the 
    # first column is 'IDOC #'.
        
    where = _df[idoc_c] == 'IDOC #'      # find header 
    header = _df.loc[where].index[0]
        
    _df.columns = _df.iloc[header]             # put correct header as header
    _df = _df.iloc[header + 1:]        # drop nan rows

    where = _df['Name'] == 'nan'
    _df.loc[~where]

    return _df.loc[:, ~_df.columns.isna()]

def type_name(_df) -> None:
        
    _df.rename(columns= {'Current Admission Type' : 'Admission Type'}, inplace = True)
    _df.rename(columns= {'Custody    Date' : 'Custody Date'}, inplace = True)
    _df.columns = _df.columns.str.strip('3')


    date_col = list(_df.columns[1:])
    date_col = [c for c in date_col if 'Date' in c]
    for c in date_col:

        wrong = _df[c]
        correct = pd.to_datetime(wrong, format='%m%d%Y', errors='coerce')
            
        _df[c] = correct


    # select cols for renaming
    _df = _df[[col for col in NAMES if col in _df.columns]]
    _df = _df.rename(columns=NAMES)

    # re-type column   
    current_types = {col: TYPES[col] for col in _df.columns if col in TYPES}
    _df = _df.astype(current_types)

    return _df

def single_excel(excel_file : str) -> pd.DataFrame:
            
    # ff the link is relative, make it absolute
    if not excel_file.startswith('http'):
        excel_file = requests.compat.urljoin(URL, excel_file)
            
    response = requests.get(excel_file) # fetch excel
    
    b = response.content
    _df = pd.read_excel(io.BytesIO(b))  
    _df = header(_df)
    _df = type_name(_df)
    xls = pd.ExcelFile(io.BytesIO(b))
    _df['record_dt'] = pd.to_datetime(xls.sheet_names[0].split(' ')[-1])      

    return _df

def clear_table(table_name : str) -> None:
    
    # upload to duckdb
    db_path = r"C:\Users\jackm\OneDrive\Documents\duckdb_cli-windows-amd64\my_database.duckdb"
    con = duckdb.connect(db_path)

    #### FUNCTION
    con.execute(f'TRUNCATE TABLE {table_name}')

    con.close()

def pandas_to_sql(dtype):
    
    if dtype.kind in {"i"}:      # integer
        return "INTEGER"
    
    if dtype.kind in {"f"}:      # float
        return "DOUBLE PRECISION"
    
    if dtype.kind in {"b"}:      # boolean
        return "BOOLEAN"
    
    if dtype.kind in {"M"}:      # datetime64
        return "TIMESTAMP"
    
    if dtype.name == "category":
        return "VARCHAR"
    
    return "VARCHAR" # fallback for object/string

def generate_create_table_sql(df_ : pd.DataFrame, table_name):
    
    
    cols = []
    for col, dtype in df_.dtypes.items():
        sql_type = pandas_to_sql(dtype)
        cols.append(f'"{col}" {sql_type}')
    
    cols_sql = ",\n  ".join(cols)

    # upload to duckdb
    db_path = r"C:\Users\jackm\OneDrive\Documents\duckdb_cli-windows-amd64\my_database.duckdb"
    con = duckdb.connect(db_path)

    con.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} ({cols_sql});
    """)

def insert_table(df_ : pd.DataFrame, table_name) -> None:

    # upload to duckdb
    db_path = r"C:\Users\jackm\OneDrive\Documents\duckdb_cli-windows-amd64\my_database.duckdb"
    con = duckdb.connect(db_path)
    con.register('df_view', df_)
    
    #### FUNCTION
    con.execute(f"""
        INSERT INTO {table_name}
        SELECT * FROM df_view;
    """)

    con.close()

def import_duckdb(table_name, conn) -> pd.DataFrame:

    query = f'SELECT * FROM {table_name}'
    conn.execute(query)

    col = [desc[0] for desc in conn.description]
    data = conn.fetchall()

    return pd.DataFrame(data = data, columns = col)

def main(str_type : str) -> None:

    sql_name = str_type.split('.')[0].replace('-', '_')
    print_type = str_type.split('-')[1][:-1].capitalize()
    excel_urls = fetch_excels(str_type)

    excel = single_excel(excel_urls[0])
    generate_create_table_sql(excel, sql_name)
    clear_table(sql_name)

    for d in tqdm(excel_urls, desc=f"Processing {print_type}"):
        
        excel = single_excel(d)
        insert_table(excel, sql_name)



# %%
