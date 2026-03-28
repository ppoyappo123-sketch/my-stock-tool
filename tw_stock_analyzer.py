import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 環境初始化 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

def fetch_json(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200:
            data = res.json()
            if data.get('stat') == 'OK': return data
    except:
        pass
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

# --- 2. Streamlit 介面 ---
st.set_page_config(page_title="台股分析精準版", layout="wide")

st.sidebar.header("功能切換")
mode = st.sidebar.selectbox("模式選擇", ["大盤單日精確查詢", "個股跨月異常分析"])

if mode == "大盤單日精確查詢":
    st.title("🏛️ 大盤單日數據掃描")
    st.info("此模式會同時對接「加權指數專表」與「成交統計表」，抓取最精確的數據。")
    
    query_date = st.date_input("選擇查詢日期", value=datetime.today() - timedelta(days=1))
    
    if st.button("🔍 執行單日分析"):
        d_str = query_date.strftime('%Y%m%d')
        
        with st.spinner(f'正在分析 {query_date.strftime("%Y-%m-%d")} 數據...'):
            # A. 抓加權指數專表 (MI_5MIN_INDICES) -> 找最高最低
            idx_url = f"https://www.twse.com.tw/exchangeReport/MI_5MIN_INDICES?response=json&date={d_str}"
            idx_data = fetch_json(idx_url)
            
            # B. 抓成交統計表 (MI_5MINS) -> 找 13:30 累積量
            vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
            vol_data = fetch_json(vol_url)
            
            if idx_data and vol_data:
                # 指數掃描 (索引 1 是發行量加權股價指數)
                indices = [safe_float(r[1]) for r in idx_data['data']]
                # 成交量掃描 (索引 5 數量, 索引 6 金額)
                target_1330 = next((r for r in vol_data['data'] if "13:30:00" in r[0]), vol_data['data'][-1])
                
                res_df = pd.DataFrame([{
                    '查詢日期': query_date.strftime('%Y-%m-%d'),
                    '加權指數最高': max(indices),
                    '加權指數最低': min(indices),
                    '13:30 累積成交數量(股)': target_1330[5],
                    '13:30 累積成交金額(百萬元)': target_1330[6]
                }])
                st.success("數據抓取成功！")
                st.table(res_df) # 單日數據用 table 顯示更清楚
            else:
                st.error("無法取得當日數據。可能是假日、尚未收盤，或連線受限。")

else:
    # --- 模式：個股跨月分析 (維持原樣) ---
    st.title("📈 個股跨月異常分析")
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_id = st.text_input("股票代號", value="2330").strip()
    with col2:
        start_date = st.date_input("開始月份", value=datetime(2025, 1, 1))
    with col3:
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始個股分析"):
        all_stock_data = []
        temp_date = start_date.replace(day=1)
        
        progress = st.progress(0)
        while temp_date <= end_date.replace(day=1):
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_json(url)
            if data:
                for r in data['data']:
                    all_stock_data.append({
                        '日期': r[0], 'turnover': safe_float(r[2]), 
                        '最高': safe_float(r[4]), '最低': safe_float(r[5]), 
                        '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)
                    })
            temp_date += relativedelta(months=1)
            time.sleep(2) # 個股跨月連線需禮貌間隔
            
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            formula_label = "成交金額/(最高-最低)/1億"
            df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.dataframe(df.style.apply(lambda row: ['background-color: #fee2e2' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
        else:
            st.error("查無個股資料，請檢查代號或日期。")
