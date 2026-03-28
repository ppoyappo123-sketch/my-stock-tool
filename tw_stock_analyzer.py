import streamlit as st
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
import random
from datetime import datetime, timedelta

# --- 1. 連線環境初始化 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

def fetch_json(url):
    for i in range(3):
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=25)
            if res.status_code == 200:
                data = res.json()
                if data.get('stat') == 'OK': return data
            elif res.status_code == 403:
                time.sleep(10)
        except: pass
        time.sleep(random.uniform(5, 8))
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

st.set_page_config(page_title="台股大盤數據工具", layout="wide")
st.title("🏛️ 大盤 13:30 數據與指數高低掃描")

# 側邊欄設定
start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=3))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行查詢"):
    all_data = []
    curr_date = start_date
    status_msg = st.empty()
    
    while curr_date <= end_date:
        if curr_date.weekday() < 5:
            d_str = curr_date.strftime('%Y%m%d')
            status_msg.write(f"📡 正在處理：{curr_date.strftime('%Y-%m-%d')}")
            
            # --- A. 抓加權指數高低點 (MI_5MIN_INDICES) ---
            idx_url = f"https://www.twse.com.tw/exchangeReport/MI_5MIN_INDICES?response=json&date={d_str}"
            idx_data = fetch_json(idx_url)
            
            # --- B. 抓 13:30 成交量/金額 (MI_5MINS) ---
            vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
            vol_data = fetch_json(vol_url)
            
            if idx_data and vol_data:
                # 1. 處理指數 (欄位[1]為加權指數)
                indices = [safe_float(r[1]) for r in idx_data['data']]
                
                # 2. 處理成交數據 (鎖定 13:30:00)
                # target[5] 累積成交數量, target[6] 累積成交金額
                target = next((r for r in vol_data['data'] if "13:30:00" in r[0]), None)
                
                if target:
                    all_data.append({
                        '交易日期': curr_date.strftime('%Y-%m-%d'),
                        '加權指數最高': max(indices),
                        '加權指數最低': min(indices),
                        '13:30 累積成交數量(股)': target[5],
                        '13:30 累積成交金額(百萬元)': target[6]
                    })
            # 兩次請求合併，需間隔稍久防鎖
            time.sleep(random.uniform(6, 9))
        
        curr_date += timedelta(days=1)

    if all_data:
        status_msg.empty()
        st.success("✅ 整合數據成功")
        st.dataframe(pd.DataFrame(all_data), use_container_width=True)
    else:
        st.error("連線受限或查無交易數據。建議區間縮短至 3 天內。")
