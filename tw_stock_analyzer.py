import streamlit as st
import pandas as pd
import requests
import time
import ssl
import urllib3
from datetime import datetime, timedelta

# --- 1. 連線設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

def get_yahoo_indices(query_date):
    """ 從 Yahoo Chart API 獲取高低點 """
    start_ts = int(time.mktime(query_date.timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={start_ts}&period2={start_ts + 86400}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        result = res['chart']['result'][0]
        high = result['indicators']['quote'][0]['high'][0]
        low = result['indicators']['quote'][0]['low'][0]
        return {'high': round(high, 2), 'low': round(low, 2)}
    except: return None

def fetch_twse_vol(date_str):
    """ 抓取證交所 13:30 數據 """
    url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={date_str}"
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        data = res.json()
        if data.get('stat') == 'OK':
            # 找到 13:30:00 的那一行
            row = next((r for r in data['data'] if "13:30:00" in r[0]), data['data'][-1])
            return row
    except: return None

# --- 2. Streamlit 介面 ---
st.title("🏛️ 大盤數據 (Yahoo 指數 + 證交所成交量)")

query_date = st.date_input("選擇日期", value=datetime(2026, 3, 27))

if st.button("🔍 執行查詢"):
    with st.spinner('數據讀取中...'):
        y_data = get_yahoo_indices(query_date)
        vol_row = fetch_twse_vol(query_date.strftime('%Y%m%d'))
        
        if y_data and vol_row:
            # --- 根據 image_7f7cfc.png 與 image_7f7d55.png 重新校對 ---
            # vol_row[5] 是 筆數 (2,860,358)
            # vol_row[6] 是 數量 (9,210,912) -> 這才是我們要的累積張數
            # vol_row[7] 是 金額 (631,122) -> 這才是我們要的累積金額
            
            res_df = pd.DataFrame([{
                '日期': query_date.strftime('%Y-%m-%d'),
                '加權最高 (Yahoo)': y_data['high'],
                '加權最低 (Yahoo)': y_data['low'],
                '13:30 累積成交數量 (股)': vol_row[6], 
                '13:30 累積成交金額 (百萬元)': vol_row[7]
            }])
            
            st.success("✅ 數據對位成功！")
            st.table(res_df)
        else:
            st.error("抓取失敗，請確認該日為交易日，或證交所連線忙碌中。")
