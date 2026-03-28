import streamlit as st
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 連線基礎設施 ---
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
            res = requests.get(url, headers=HEADERS, verify=False, timeout=30)
            if res.status_code == 200:
                data = res.json()
                if data.get('stat') == 'OK': return data
        except: pass
        time.sleep(random.uniform(5, 8))
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

st.set_page_config(page_title="台股分析工具", layout="wide")

st.sidebar.header("功能設定")
mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤精確數據(13:30)"])
start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=3))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行分析"):
    all_data = []
    
    if mode == "個股跨月分析":
        # ... (個股邏輯保持不變) ...
        pass
    else:
        # --- 大盤模式：雙來源合併 ---
        curr_date = start_date
        while curr_date <= end_date:
            if curr_date.weekday() < 5:
                d_str = curr_date.strftime('%Y%m%d')
                st.write(f"正在整合 {d_str} 數據...")
                
                # A. 抓加權指數 (MI_5MIN_INDICES) -> 取得全日最高最低
                idx_url = f"https://www.twse.com.tw/exchangeReport/MI_5MIN_INDICES?response=json&date={d_str}"
                idx_data = fetch_json(idx_url)
                
                # B. 抓成交統計 (MI_5MINS) -> 取得 13:30 累積量/金額
                vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                vol_data = fetch_json(vol_url)
                
                if idx_data and vol_data:
                    # 1. 指數分析：從 MI_5MIN_INDICES 的 r[1] 抓加權指數
                    all_indices = [safe_float(r[1]) for r in idx_data['data']]
                    day_high = max(all_indices) if all_indices else 0
                    day_low = min(all_indices) if all_indices else 0
                    
                    # 2. 成交量分析：從 MI_5MINS 抓 13:30:00 累積數據
                    # r[4] 是累積成交量(股), r[6] 是累積成交金額(元)
                    target = next((r for r in vol_data['data'] if "13:30:00" in r[0]), vol_data['data'][-1])
                    
                    all_data.append({
                        '交易日期': curr_date.strftime('%Y-%m-%d'),
                        '加權指數最高': day_high,
                        '加權指數最低': day_low,
                        '13:30累積金額(億)': round(safe_float(target[6]) / 100000000, 2),
                        '13:30累積量(張)': int(safe_float(target[5]) / 1000)
                    })
                time.sleep(random.uniform(4, 6))
            curr_date += timedelta(days=1)

        if all_data:
            st.dataframe(pd.DataFrame(all_data), use_container_width=True)
        else:
            st.error("連線受限或查無資料，請縮短日期區間。")
