import streamlit as st
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
import random
from datetime import datetime, timedelta

# --- 1. 連線基礎設定 (解決 SSL 問題) ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/zh/trading/historical/mi-5mins.html'
}

def fetch_json(url):
    for i in range(3):
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
            if res.status_code == 200:
                data = res.json()
                if data.get('stat') == 'OK': return data
        except: pass
        time.sleep(random.uniform(5, 8))
    return None

st.set_page_config(page_title="大盤數據查詢", layout="wide")

st.title("🏛️ 大盤 13:30 累積成交數據")
st.caption("數據來源：證交所每5秒委託買賣統計 (單位對應網頁：百萬元、交易單位)")

# 側邊欄設定
start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=3))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行查詢"):
    all_data = []
    curr_date = start_date
    status_msg = st.empty()
    
    while curr_date <= end_date:
        if curr_date.weekday() < 5: # 僅平日
            d_str = curr_date.strftime('%Y%m%d')
            status_msg.write(f"📡 抓取中：{curr_date.strftime('%Y-%m-%d')}")
            
            url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
            raw = fetch_json(url)
            
            if raw and 'data' in raw:
                # 尋找 13:30:00 這一列
                # 根據圖 6：索引 5 是累積成交數量(股)，索引 6 是累積成交金額(百萬元)
                target = next((r for r in raw['data'] if "13:30:00" in r[0]), None)
                
                if target:
                    all_data.append({
                        '交易日期': curr_date.strftime('%Y-%m-%d'),
                        '時間': '13:30:00',
                        '累積成交數量 (股)': target[5],
                        '累積成交金額 (百萬元)': target[6]
                    })
            time.sleep(random.uniform(5, 7)) # 避免 IP 被鎖
        curr_date += timedelta(days=1)

    if all_data:
        status_msg.empty()
        st.success("✅ 數據提取成功")
        # 顯示表格
        st.dataframe(pd.DataFrame(all_data), use_container_width=True)
    else:
        st.error("連線受限或此區間無交易數據。")
