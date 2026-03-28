import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta

# --- 1. 連線基礎設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

def fetch_twse_json(url):
    """ 萬用證交所 JSON 抓取器 """
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
st.title("🏛️ 加權指數專表掃描 + 13:30 成交數據")

# 側邊欄日期設定
start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=3))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行精確查詢"):
    all_results = []
    curr_date = start_date
    status_msg = st.empty()
    
    while curr_date <= end_date:
        if curr_date.weekday() < 5:
            d_str = curr_date.strftime('%Y%m%d')
            status_msg.write(f"📡 正在處理：{curr_date.strftime('%Y-%m-%d')}")
            
            # --- A. 抓加權指數專表 (MI_5MIN_INDICES) ---
            # 這是抓 https://www.twse.com.tw/zh/indices/taiex/mi-5min-indices.html
            idx_url = f"https://www.twse.com.tw/exchangeReport/MI_5MIN_INDICES?response=json&date={d_str}"
            idx_json = fetch_twse_json(idx_url)
            
            # --- B. 抓 13:30 成交數據 (MI_5MINS) ---
            # 這是抓 https://www.twse.com.tw/zh/trading/historical/mi-5mins.html
            vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
            vol_json = fetch_twse_json(vol_url)
            
            if idx_json and vol_json and 'data' in idx_json and 'data' in vol_json:
                # 1. 掃描加權指數 (專表的索引 1 是加權指數)
                indices = [safe_float(r[1]) for r in idx_json['data']]
                
                # 2. 捕捉 13:30:00 成交量與金額
                target_1330 = next((r for r in vol_json['data'] if "13:30:00" in r[0]), vol_json['data'][-1])
                
                all_results.append({
                    '交易日期': curr_date.strftime('%Y-%m-%d'),
                    '加權指數最高': max(indices) if indices else 0,
                    '加權指數最低': min(indices) if indices else 0,
                    '13:30 累積成交數量(股)': target_1330[5],
                    '13:30 累積成交金額(百萬元)': target_1330[6]
                })
            
            # 同一天抓兩次 API，必須間隔較久以防被鎖 IP
            time.sleep(random.uniform(7, 10))
            
        curr_date += timedelta(days=1)

    if all_results:
        status_msg.empty()
        st.success("✅ 整合數據成功！")
        st.dataframe(pd.DataFrame(all_results), use_container_width=True)
    else:
        st.error("連線受限或查無資料。")
