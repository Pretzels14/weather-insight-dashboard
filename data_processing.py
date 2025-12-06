import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import os
import logging

def ensure_cache_table(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS climate_monthly_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            avg_temp REAL,
            total_precip REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(city, month, year)
        );
    ''')
    conn.commit()
    conn.close()

def save_daily_records_to_db(db_path, city, daily_records):

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS climate_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            date TEXT NOT NULL,
            temp REAL,
            precipitation REAL,
            source TEXT,
            UNIQUE(city, date)
        );
    ''')
    for rec in daily_records:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO climate_daily (city, date, temp, precipitation, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (city, rec['date'], rec.get('temp'), rec.get('precip'), 'api'))
        except Exception as e:
            logging.error(f"Failed to upsert daily record {rec}: {e}")
    conn.commit()
    conn.close()

def read_daily_records(db_path, city, start_date=None, end_date=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    sql = "SELECT date, temp, precipitation FROM climate_daily WHERE city = ?"
    params = [city]
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " ORDER BY date ASC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    # return as DataFrame
    df = pd.DataFrame(rows, columns=['date', 'temp', 'precip'])
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

def compute_monthly_from_db(db_path, city, years=30):
    end = datetime.utcnow().date()
    start = end.replace(year=end.year - years)
    df = read_daily_records(db_path, city, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    if df.empty:
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        return months, [None]*12, [None]*12

    df['month'] = df['date'].dt.month
    monthly = df.groupby('month').agg(avg_temp=('temp','mean')).reset_index()

    full = pd.DataFrame({'month':range(1,13)})
    merged = pd.merge(full, monthly, on="month", how="left")

    months = merged['month'].apply(lambda m: datetime(2000,m,1).strftime('%b')).tolist()
    avg_temps = merged['avg_temp'].round(2).replace({np.nan: None}).tolist()
    avg_precips = [None]*12

    return months, avg_temps, avg_precips


def compute_monthly_averages(db_path, city, years=30):
        """
        Reads monthly climate normals from local CSV first.
        If not available, fallback to DB-based synthetic/historical.
        """

        csv_path = os.path.join(os.path.dirname(__file__), "data", "climate_normals.csv")

        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            df_city = df[df["city"].str.lower() == city.lower()]

            if not df_city.empty:
                months = df_city["month"].apply(lambda m: datetime(2000, m, 1).strftime("%b")).tolist()
                avg_temps = df_city["avg_temp_f"].tolist()
                avg_precips = [None] * 12  # (optional: add precip later)
                return months, avg_temps, avg_precips

        # No CSV match — use DB historical or synthetic fallback
        return compute_monthly_from_db(db_path, city, years)


def read_cached_monthly_averages(db_path, city, years=30):

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT month, avg_temp, total_precip, year FROM climate_monthly_cache WHERE city = ?", (city,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    # aggregate into months order (1..12) picking latest year values / or average across years
    df = pd.DataFrame(rows, columns=['month','avg_temp','total_precip','year'])
    df = df.groupby('month').agg(avg_temp=('avg_temp','mean'), avg_precip=('total_precip','mean')).reset_index()
    months = df['month'].apply(lambda m: datetime(2000, m, 1).strftime('%b')).tolist()
    avg_temps = df['avg_temp'].round(2).replace({np.nan: None}).tolist()
    avg_precips = df['avg_precip'].round(2).replace({np.nan: None}).tolist()
    return {"months": months, "avg_temps": avg_temps, "avg_precips": avg_precips}
