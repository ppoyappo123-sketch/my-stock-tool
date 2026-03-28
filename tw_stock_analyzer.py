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
            elif res.status_code == 403: # 被封鎖時等待久一點
                time.sleep(10)
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
        # (個股邏輯維持之前成功版本，如圖 4、圖 5 樣式)
        stock_id = st.sidebar.text_input("代號", value="2330", key="stock_id").strip()
        st.info("執行個股多月份分析中...")
        # ...此處省略個股代碼以保持簡潔...
    else:
        # --- 大盤模式：單一來源掃描 (解決連線受限問題) ---
        curr_date = start_date
        status_area = st.empty()
        
        while curr_date <= end_date:
            if curr_date.weekday() < 5:
                d_str = curr_date.strftime('%Y%m%d')
                status_area.write(f"📡 正在掃描 {d_str} 全日每 5 秒數據...")
                
                # 抓取 MI_5MINS (這張表同時有指數、成交量、成交金額)
                url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                raw_data = fetch_json(url)
                
                if raw_data and 'data' in raw_data:
                    data_rows = raw_data['data']
                    
                    # 1. 整理「台股加權指數」最高與最低 (r[1] 是發行量加權股價指數)
                    # 遍歷整天 5 秒數據找高低點
                    all_indices = [safe_float(r[1]) for r in data_rows]
                    
                    # 2. 鎖定「13:30:00」那一刻的累積數據
                    # r[5] 是累積成交股數, r[6] 是累積成交金額
                    target_1330 = next((r for r in data_rows if "13:30:00" in r[0]), data_rows[-1])
                    
                    all_data.append({
                        '交易日期': curr_date.strftime('%Y-%m-%d'),
                        '加權指數最高': max(all_indices),
                        '加權指數最低': min(all_indices),
                        '13:30 累積金額(億)': round(safe_float(target_1330[6]) / 100000000, 2),
                        '13:30 累積量(張)': int(safe_float(target_1330[5]) / 1000)
                    })
                time.sleep(random.uniform(5, 7)) # 增加隨機延遲模擬真人
            curr_date += timedelta(days=1)

        if all_data:
            st.success("✅ 大盤數據整合完成！")
            st.dataframe(pd.DataFrame(all_data), use_container_width=True)
        else:
            st.error("連線受限或查無資料。建議日期區間不要超過 5 天。")
