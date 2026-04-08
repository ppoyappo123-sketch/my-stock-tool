import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎安全性設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

# --- 2. 數據抓取核心函式 ---

def fetch_json(url):
    """ 通用 JSON 抓取器 """
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def safe_float(val):
    """ 清理字串並轉為浮點數 """
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

def get_yahoo_stock_data(stock_id, start_date, end_date):
    """ Yahoo Finance 抓取器 (專用於上櫃) """
    symbol = f"{stock_id}.TWO"
    start_ts = int(time.mktime(start_date.timetuple()))
    end_ts = int(time.mktime((end_date + timedelta(days=1)).timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start_ts}&period2={end_ts}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15).json()
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        quote = result['indicators']['quote'][0]
        data = []
        for i in range(len(timestamps)):
            dt = datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d')
            c, v, h, l = quote['close'][i], quote['volume'][i], quote['high'][i], quote['low'][i]
            if c and v and v > 0:
                data.append({'日期': dt, '成交量(張)': int(v / 1000), 'turnover': v * c, '最高': round(h, 2), '最低': round(l, 2), '收盤': round(c, 2)})
        return data
    except: return None

def get_yahoo_indices(query_date):
    """ 大盤點數抓取 """
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
st.set_page_config(page_title="台股全方位分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (原版證交所)", "上櫃個股分析 (Yahoo穩定版)"],
    key="nav_v9" 
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 (維持 13:30 對位邏輯) ---
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
                status.write(f"📡 抓取大盤數據：{d.strftime('%Y-%m-%d')}")
                y = get_yahoo_indices(d)
                v = fetch_json(f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}")
                if y and v and v.get('stat') == 'OK':
                    row = next((r for r in v['data'] if "13:30:00" in r[0]), v['data'][-1])
                    score = (safe_float(row[7])/100 / (y['high'] - y['low'])) if (y['high'] - y['low']) > 0 else 0
                    all_results.append({'交易日期': d.strftime('%Y-%m-%d'), '加權最高': y['high'], '加權最低': y['low'], '13:30累積金額(百萬)': row[7], formula_label: round(score, 4)})
                progress.progress((i + 1) / len(date_list)); time.sleep(random.uniform(1.2, 2.0))
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results); avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 5. 模式 B：上市個股分析 (恢復原版證交所邏輯) ---
elif mode == "上市個股分析 (原版證交所)":
    st.title("📈 上市個股分析 (TWSE 官方數據)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始上市分析"):
        all_stock_data = []
        months_to_fetch = []
        temp_date = start_month.replace(day=1)
        while temp_date <= end_date.replace(day=1):
            months_to_fetch.append(temp_date); temp_date += relativedelta(months=1)
        
        progress = st.progress(0); status = st.empty()
        for i, target_month in enumerate(months_to_fetch):
            status.write(f"📡 抓取證交所數據：{target_month.strftime('%Y-%m')}")
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={target_month.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_json(url)
            if data and data.get('stat') == 'OK':
                for r in data['data']:
                    all_stock_data.append({'日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)})
            progress.progress((i + 1) / len(months_to_fetch)); time.sleep(2)
        status.empty()
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.success(f"✅ {stock_id} 上市分析完成")
            display_cols = ['日期', '成交量(張)', '成交金額(億元)', '最高', '最低', '收盤', formula_label, '3倍異常']
            st.dataframe(df[display_cols].style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 6. 模式 C：上櫃個股分析 (使用 Yahoo 穩定抓取) ---
else:
    st.title("📉 上櫃個股分析 (Yahoo Finance)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="8046")
    with col2: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃分析"):
        with st.spinner('從 Yahoo 獲取數據中...'):
            data = get_yahoo_stock_data(stock_id, start_d, end_d)
        if data:
            df = pd.DataFrame(data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.success(f"✅ {stock_id} 上櫃分析完成")
            display_cols = ['日期', '成交量(張)', '成交金額(億元)', '最高', '最低', '收盤', formula_label, '3倍異常']
            st.dataframe(df[display_cols].style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("抓取失敗，請確認代號是否正確。")
