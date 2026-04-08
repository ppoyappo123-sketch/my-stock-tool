import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎安全性與環境設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://finance.yahoo.com/'
}

# --- 2. 數據抓取工具函式 ---

def fetch_json(url):
    """ 通用 JSON 抓取器 """
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

def get_yahoo_stock_data(stock_id, start_date, end_date):
    """ 從 Yahoo Finance 抓取個股歷史數據 (支援上市/上櫃) """
    # 台灣股票代號需補上 .TW (上市) 或 .TWO (上櫃)
    # 這裡預設為上櫃模式使用 .TWO
    symbol = f"{stock_id}.TWO"
    start_ts = int(time.mktime(start_date.timetuple()))
    end_ts = int(time.mktime(end_date.timetuple()))
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start_ts}&period2={end_ts}&interval=1d"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=15).json()
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        indicators = result['indicators']['quote'][0]
        
        data = []
        for i in range(len(timestamps)):
            dt = datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d')
            # Yahoo 的金額單位通常是原始數值，成交量是「股」
            # 我們需要：成交金額 = 成交量 * 收盤價 (概估) 或 直接取 Volume
            # 註：Yahoo API 不直接提供每日「成交金額」，通常用 (Volume * Close) 估算
            close = safe_float(indicators['close'][i])
            vol = safe_float(indicators['volume'][i])
            high = safe_float(indicators['high'][i])
            low = safe_float(indicators['low'][i])
            
            if vol > 0:
                data.append({
                    '日期': dt,
                    '成交量(張)': int(vol / 1000),
                    '估算成交金額': vol * close,
                    '最高': round(high, 2),
                    '最低': round(low, 2),
                    '收盤': round(close, 2)
                })
        return data
    except Exception as e:
        st.error(f"Yahoo 抓取失敗: {e}")
        return None

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
st.set_page_config(page_title="台股分析工具 (Yahoo穩定版)", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (Yahoo Finance)"],
    key="nav_v6" 
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 (原樣) ---
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (Yahoo + 證交所對位)")
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤分析"):
        all_results = []
        date_list = [start_d + timedelta(days=x) for x in range((end_d-start_d).days + 1) if (start_d + timedelta(days=x)).weekday() < 5]
        if date_list:
            progress = st.progress(0); status = st.empty()
            for i, d in enumerate(date_list):
                status.write(f"📡 抓取大盤：{d.strftime('%Y-%m-%d')}")
                y = get_yahoo_indices(d)
                v_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}"
                v = fetch_json(v_url)
                if y and v and v.get('stat') == 'OK':
                    row = next((r for r in v['data'] if "13:30:00" in r[0]), v['data'][-1])
                    score = (safe_float(row[7])/100 / (y['high'] - y['low'])) if (y['high'] - y['low']) > 0 else 0
                    all_results.append({'交易日期': d.strftime('%Y-%m-%d'), '加權最高': y['high'], '加權最低': y['low'], '13:30累積金額(百萬)': row[7], formula_label: round(score, 4)})
                progress.progress((i + 1) / len(date_list)); time.sleep(1.2)
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results); avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 5. 模式 B：上市個股分析 (原樣) ---
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE)")
    col1, col2 = st.columns(2)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: query_month = st.date_input("查詢月份", value=datetime.today())

    if st.button("🚀 開始分析"):
        res = fetch_json(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={query_month.strftime('%Y%m%d')}&stockNo={stock_id}")
        if res and res.get('stat') == 'OK':
            df = pd.DataFrame(res['data'], columns=["日期", "成交股數", "成交金額", "開盤", "最高", "最低", "收盤", "漲跌", "成交筆數"])
            df['金額'] = df['成交金額'].apply(safe_float)
            df['最高'] = df['最高'].apply(safe_float)
            df['最低'] = df['最低'].apply(safe_float)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 6. 模式 C：上櫃個股專屬分析 (Yahoo Finance 版) ---
else:
    st.title("📉 上櫃個股分析 (Yahoo Finance)")
    st.info("透過 Yahoo Finance 獲取上櫃/興櫃歷史數據，穩定且不限頻率。")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="8046")
    with col2: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行 Yahoo 抓取"):
        with st.spinner('正在從 Yahoo Finance 讀取數據...'):
            data_list = get_yahoo_stock_data(stock_id, start_d, end_d)
        
        if data_list:
            df = pd.DataFrame(data_list)
            # 公式：成交金額(估算)/(最高-最低)/1億
            df[formula_label] = df.apply(lambda r: (r['估算成交金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            
            # 格式優化
            df['成交金額(億)'] = (df['估算成交金額'] / 100000000).round(2)
            display_cols = ['日期', '成交量(張)', '成交金額(億)', '最高', '最低', '收盤', formula_label, '3倍異常']
            
            st.success(f"✅ {stock_id}.TWO 數據獲取成功")
            st.dataframe(df[display_cols].style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("無法取得數據，請確認代號是否正確 (上櫃代號不需加 .TWO，程式會自動補上)。")
