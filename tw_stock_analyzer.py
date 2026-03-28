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

# --- 1. 基礎連線防護 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.twse.com.tw/'
}

# 核心抓取函式 (增加穩定性)
def fetch_json(url):
    for i in range(3): # 重試 3 次
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
            if res.status_code == 200:
                data = res.json()
                if data.get('stat') == 'OK':
                    return data
            elif res.status_code == 403: # 被封鎖
                time.sleep(10)
        except:
            pass
        time.sleep(random.uniform(3, 6))
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

st.set_page_config(page_title="台股分析工具", layout="wide")

st.sidebar.header("功能設定")
analysis_mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤精確數據(13:30)"])

# 日期選擇
if analysis_mode == "個股跨月分析":
    start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
    stock_id = st.sidebar.text_input("股票代號", value="2330").strip()
else:
    # 大盤建議一次不要查超過 10 天，否則容易被鎖 IP
    start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=5))
    stock_id = None

end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行分析"):
    all_data = []
    
    if analysis_mode == "個股跨月分析":
        with st.spinner('正在分析個股...'):
            temp_date = start_date.replace(day=1)
            while temp_date <= end_date.replace(day=1):
                url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
                data = fetch_json(url)
                if data:
                    for r in data['data']:
                        all_data.append({
                            '日期': r[0], 'capacity': safe_float(r[1]), 'turnover': safe_float(r[2]), 
                            '開盤': safe_float(r[3]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), 
                            '收盤': safe_float(r[6]), '漲跌': r[7]
                        })
                temp_date += relativedelta(months=1)
                time.sleep(2)
            
            if all_data:
                df = pd.DataFrame(all_data)
                df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                formula_label = "成交金額/(最高-最低)/1億"
                df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
                res_label = "指標結果(x1億)"
                df[res_label] = (df[formula_label] * 100000000).round(2)
                avg_val = df[formula_label].mean()
                df['3倍異常'] = df[formula_label] > (avg_val * 3)
                st.dataframe(df.style.apply(lambda row: ['background-color: #fee2e2' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)

    else:
        # --- 模式 B: 大盤 13:30 (整合兩個來源) ---
        progress_bar = st.progress(0)
        curr_date = start_date
        date_range = (end_date - start_date).days + 1
        processed_days = 0

        while curr_date <= end_date:
            if curr_date.weekday() < 5:
                d_str = curr_date.strftime('%Y%m%d')
                st.write(f"正在抓取 {curr_date.strftime('%Y-%m-%d')} ...")
                
                # 來源 1: 最高/最低指數
                idx_url = f"https://www.twse.com.tw/exchangeReport/MI_5MIN_INDICES?response=json&date={d_str}"
                idx_json = fetch_json(idx_url)
                
                # 來源 2: 13:30 成交量/金額
                vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                vol_json = fetch_json(vol_url)
                
                if idx_json and vol_json:
                    indices = [safe_float(r[1]) for r in idx_json['data']]
                    # 抓 13:30:00，抓不到就抓最後一筆
                    target_vol = next((r for r in vol_json['data'] if "13:30:00" in r[0]), vol_json['data'][-1])
                    
                    all_data.append({
                        '交易日期': curr_date.strftime('%Y-%m-%d'),
                        '當日最高指數': max(indices) if indices else 0,
                        '當日最低指數': min(indices) if indices else 0,
                        '13:30累積金額(億)': round(safe_float(target_vol[4]) / 100000000, 2),
                        '13:30累積量(張)': int(safe_float(target_vol[3]) / 1000)
                    })
                time.sleep(random.uniform(3, 5)) # 禮貌延遲

            processed_days += 1
            progress_bar.progress(processed_days / date_range)
            curr_date += timedelta(days=1)

        if all_data:
            st.success("✅ 大盤數據抓取完成！")
            st.dataframe(pd.DataFrame(all_data), use_container_width=True)
        else:
            st.error("❌ 抓不到資料。可能是假日、尚未開盤，或連線被證交所暫時阻擋。")
