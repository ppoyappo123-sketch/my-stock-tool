import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 安全性與環境設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

# --- 2. 數據抓取核心工具 ---

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

def fetch_twse(url):
    """ 專用於證交所與 Yahoo 的抓取器 """
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200: return res.json()
    except: return None

def fetch_tpex(stock_id, query_date):
    """ 專用於櫃買中心 (TPEx) 的強效抓取器 """
    roc_year = query_date.year - 1911
    d_str = f"{roc_year}/{query_date.strftime('%m')}/01"
    url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={d_str}&stk_code={stock_id}"
    
    tpex_headers = HEADERS.copy()
    tpex_headers['Referer'] = 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html'
    
    try:
        res = requests.get(url, headers=tpex_headers, verify=False, timeout=15)
        if res.status_code == 200: return res.json()
    except: return None

def get_yahoo_indices(query_date):
    start_ts = int(time.mktime(query_date.timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={start_ts}&period2={start_ts + 86400}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        result = res['chart']['result'][0]
        high = result['indicators']['quote'][0]['high'][0]
        low = result['indicators']['quote'][0]['low'][0]
        return {'high': round(high, 2), 'low': round(low, 2)}
    except: return None

# --- 3. Streamlit 介面佈局 ---
st.set_page_config(page_title="台股全能分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買官網直連)"],
    key="nav_v8" 
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 ---
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (Yahoo + 證交所對位)")
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤分析", key="btn_m"):
        all_results = []
        date_list = [start_d + timedelta(days=x) for x in range((end_d-start_d).days + 1) if (start_d + timedelta(days=x)).weekday() < 5]
        if date_list:
            progress = st.progress(0); status = st.empty()
            for i, d in enumerate(date_list):
                status.write(f"📡 抓取大盤：{d.strftime('%Y-%m-%d')}")
                y = get_yahoo_indices(d)
                v = fetch_twse(f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}")
                if y and v and v.get('stat') == 'OK':
                    row = next((r for r in v['data'] if "13:30:00" in r[0]), v['data'][-1])
                    score = (safe_float(row[7])/100 / (y['high'] - y['low'])) if (y['high'] - y['low']) > 0 else 0
                    all_results.append({'交易日期': d.strftime('%Y-%m-%d'), '加權最高': y['high'], '加權最低': y['low'], '13:30累積金額(百萬)': row[7], formula_label: round(score, 4)})
                progress.progress((i + 1) / len(date_list)); time.sleep(1.2)
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results); avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 5. 模式 B：上市個股分析 (已修正為開始/結束模式) ---
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股跨月分析 (TWSE)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 執行上市分析", key="btn_s"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr); curr += relativedelta(months=1)
        
        progress = st.progress(0); status = st.empty()
        for i, m in enumerate(months):
            status.write(f"📡 正在從證交所抓取：{m.strftime('%Y-%m')}")
            res = fetch_twse(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={m.strftime('%Y%m%d')}&stockNo={stock_id}")
            if res and res.get('stat') == 'OK':
                for r in res['data']:
                    data_list.append({
                        '日期': r[0], 
                        '金額': safe_float(r[2]), 
                        '最高': safe_float(r[4]), 
                        '最低': safe_float(r[5]), 
                        '收盤': safe_float(r[6]), 
                        '量(張)': int(safe_float(r[1])/1000)
                    })
            progress.progress((i + 1) / len(months)); time.sleep(2)
        status.empty()
        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            st.success(f"✅ {stock_id} 上市數據抓取完成")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("查無資料，請確認股票代號。")

# --- 6. 模式 C：上櫃個股分析 ---
else:
    st.title("📉 上櫃個股分析 (TPEx 官網直連)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="8046")
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行櫃買抓取", key="btn_t"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr); curr += relativedelta(months=1)
            
        progress = st.progress(0); status = st.empty()
        for i, m in enumerate(months):
            status.write(f"📡 正在從櫃買中心抓取：{m.strftime('%Y-%m')}")
            res = fetch_tpex(stock_id, m)
            if res and res.get('aaData'):
                for r in res['aaData']:
                    data_list.append({'日期': r[0], '金額': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '量(張)': int(safe_float(r[1]))})
            progress.progress((i + 1) / len(months)); time.sleep(2.5)
        status.empty()
        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            st.success(f"✅ {stock_id} 上櫃數據抓取完成")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
