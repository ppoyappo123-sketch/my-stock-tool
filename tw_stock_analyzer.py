import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

# --- 2. 數據抓取函式 ---

def get_yahoo_indices(query_date):
    """ 從 Yahoo Chart API 獲取高低點 (穩定且快) """
    start_ts = int(time.mktime(query_date.timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={start_ts}&period2={start_ts + 86400}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        result = res['chart']['result'][0]
        high = result['indicators']['quote'][0]['high'][0]
        low = result['indicators']['quote'][0]['low'][0]
        return {'high': round(high, 2), 'low': round(low, 2)}
    except:
        return None

def fetch_twse_json(url):
    """ 萬用證交所 JSON 抓取器 """
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

# --- 3. Streamlit 介面 ---
st.set_page_config(page_title="台股全能分析工具", layout="wide")

st.sidebar.header("功能選擇")
mode = st.sidebar.selectbox("切換模式", ["大盤多日數據查詢", "個股跨月異常分析"])

if mode == "大盤多日數據查詢":
    st.title("🏛️ 大盤數據搜索 (Yahoo 指數 + 證交所成交量)")
    st.info("此功能會整合 Yahoo Finance 的高低點與證交所 13:30 的累積成交量。")
    
    col1, col2 = st.columns(2)
    with col1:
        start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=5))
    with col2:
        end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤搜索"):
        all_results = []
        curr_d = start_d
        date_list = []
        
        # 建立交易日列表 (過濾週末)
        while curr_d <= end_d:
            if curr_d.weekday() < 5:
                date_list.append(curr_d)
            curr_d += timedelta(days=1)
        
        if not date_list:
            st.warning("選取區間內無交易日。")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, d in enumerate(date_list):
                status_text.write(f"📡 正在抓取 {d.strftime('%Y-%m-%d')} ...")
                
                # 1. 抓 Yahoo 高低點
                y_data = get_yahoo_indices(d)
                
                # 2. 抓證交所 13:30 數據
                d_str = d.strftime('%Y%m%d')
                vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                vol_data = fetch_twse_json(vol_url)
                
                if y_data and vol_data:
                    # 精確對位：索引 6 為張數，索引 7 為金額
                    row_1330 = next((r for r in vol_data['data'] if "13:30:00" in r[0]), vol_data['data'][-1])
                    all_results.append({
                        '交易日期': d.strftime('%Y-%m-%d'),
                        '加權最高': y_data['high'],
                        '加權最低': y_data['low'],
                        '13:30 累積數量(股)': row_1330[6],
                        '13:30 累積金額(百萬元)': row_1330[7]
                    })
                
                # 更新進度條
                progress_bar.progress((i + 1) / len(date_list))
                # 禮貌延遲防封鎖
                time.sleep(random.uniform(2, 4))
            
            status_text.empty()
            if all_results:
                st.success(f"✅ 成功完成 {len(all_results)} 天數據整合")
                st.dataframe(pd.DataFrame(all_results), use_container_width=True)
            else:
                st.error("查無數據，請確認日期區間是否正確。")

else:
    # --- 模式：個股跨月分析 ---
    st.title("📈 個股跨月異常分析")
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_id = st.text_input("股票代號", value="2330").strip()
    with col2:
        start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3:
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始個股分析"):
        all_stock_data = []
        temp_date = start_month.replace(day=1)
        
        while temp_date <= end_date.replace(day=1):
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_twse_json(url)
            if data:
                for r in data['data']:
                    all_stock_data.append({
                        '日期': r[0], 'turnover': safe_float(r[2]), 
                        '最高': safe_float(r[4]), '最低': safe_float(r[5]), 
                        '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)
                    })
            temp_date += relativedelta(months=1)
            time.sleep(2)
            
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            formula_label = "成交金額/(最高-最低)/1億"
            df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.dataframe(df.style.apply(lambda row: ['color: #ef4444; font-weight: bold;' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
        else:
            st.error("查無個股資料。")
