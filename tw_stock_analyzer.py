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
        quote = res['chart']['result'][0]['indicators']['quote'][0]
        return {'high': round(quote['high'][0], 2), 'low': round(quote['low'][0], 2)}
    except: return None

def fetch_twse_vol(date_str):
    """ 抓取證交所 13:30 數據 """
    url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={date_str}"
    try:
        data = requests.get(url, headers=HEADERS, verify=False, timeout=20).json()
        if data.get('stat') == 'OK':
            # 找到 13:30:00 的那一行
            row = next((r for r in data['data'] if "13:30:00" in r[0]), data['data'][-1])
            return row
    except: return None

# --- 2. Streamlit 介面 ---
st.title("🏛️ 大盤數據精確對位版")

query_date = st.date_input("選擇日期", value=datetime(2026, 3, 27))

if st.button("🔍 執行對位查詢"):
    with st.spinner('數據比對中...'):
        y_data = get_yahoo_indices(query_date)
        vol_row = fetch_twse_vol(query_date.strftime('%Y%m%d'))
        
        if y_data and vol_row:
            # --- 關鍵修正處 ---
            # 根據 image_7f7cfc.png 顯示，索引 5 是筆數
            # 累積成交數量 (股) 應為索引 7 (網頁第 7 欄)
            # 累積成交金額 (百萬元) 應為索引 8 (網頁第 8 欄)
            
            res_df = pd.DataFrame([{
                '日期': query_date.strftime('%Y-%m-%d'),
                '加權最高(Yahoo)': y_data['high'],
                '加權最低(Yahoo)': y_data['low'],
                '累積成交數量(股)': vol_row[7], # 修正對位
                '累積成交金額(百萬元)': vol_row[8] # 修正對位
            }])
            
            st.success("✅ 欄位已重新對齊！")
            st.table(res_df)
            
            # 除錯用：顯示原始數據列，若還不對請截圖這一行
            with st.expander("查看原始數據索引 (除錯用)"):
                st.write(vol_row)
        else:
            st.error("抓取失敗，請確認該日為交易日。")
