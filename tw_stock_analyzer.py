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
    'Referer': 'https://www.twse.com.tw/zh/trading/historical/mi-5mins.html'
}

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

def fetch_twse_data(date_str):
    """ 抓取證交所每5秒統計資料 """
    url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={date_str}"
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

# --- 2. Streamlit 介面 ---
st.set_page_config(page_title="台股大盤精確工具", layout="wide")
st.title("🏛️ 大盤全日最高最低掃描 + 13:30 成交量")

start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=3))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 開始執行掃描"):
    all_results = []
    curr_date = start_date
    status_msg = st.empty()
    
    while curr_date <= end_date:
        if curr_date.weekday() < 5:
            d_str = curr_date.strftime('%Y%m%d')
            status_msg.write(f"📡 正在掃描並分析數據：{curr_date.strftime('%Y-%m-%d')}")
            
            raw_json = fetch_twse_data(d_str)
            
            if raw_json and 'data' in raw_json:
                data_list = raw_json['data']
                
                # --- 核心邏輯：掃描全日數據 ---
                day_indices = []
                target_1330 = None
                
                for row in data_list:
                    # 1. 收集指數 (索引 1 是加權指數)
                    current_idx = safe_float(row[1])
                    if current_idx > 0:
                        day_indices.append(current_idx)
                    
                    # 2. 捕捉 13:30:00 的成交數據
                    if "13:30:00" in row[0]:
                        target_1330 = row
                
                # 如果剛好沒抓到 13:30:00，就拿當天最後一筆
                if not target_1330:
                    target_1330 = data_list[-1]
                
                if day_indices:
                    all_results.append({
                        '交易日期': curr_date.strftime('%Y-%m-%d'),
                        '加權指數最高': max(day_indices),
                        '加權指數最低': min(day_indices),
                        '13:30 累積成交數量(股)': target_1330[5],
                        '13:30 累積成交金額(百萬元)': target_1330[6]
                    })
                
            # 延遲防鎖
            time.sleep(random.uniform(5, 7))
        
        curr_date += timedelta(days=1)

    if all_results:
        status_msg.empty()
        st.success("✅ 全日數據掃描完成！")
        st.dataframe(pd.DataFrame(all_results), use_container_width=True)
    else:
        st.error("連線受限或查無資料。請縮短日期區間試試看。")
