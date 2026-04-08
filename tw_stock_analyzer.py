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
    'Referer': 'https://www.tpex.org.tw/'
}

# --- 2. 數據抓取核心函式 ---

def fetch_json(url):
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

def get_yahoo_indices(query_date):
    """ 大盤點數抓取 (Yahoo) """
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
st.set_page_config(page_title="台股即時分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買中心)"],
    key="nav_v11" 
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 ---
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (Yahoo點數 + 證交所13:30量)")
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
                progress.progress((i + 1) / len(date_list)); time.sleep(1.5)
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results); avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
                # 套用新版 width='stretch'
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), width='stretch')

# --- 5. 模式 B：上市個股分析 (證交所) ---
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE 官方數據)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始上市分析"):
        all_stock_data = []
        temp_date = start_month.replace(day=1)
        while temp_date <= end_date:
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_json(url)
            if data and data.get('stat') == 'OK':
                for r in data['data']:
                    d_parts = r[0].split('/')
                    ad_date = datetime(int(d_parts[0])+1911, int(d_parts[1]), int(d_parts[2])).date()
                    if start_month <= ad_date <= end_date:
                        all_stock_data.append({'日期': ad_date.strftime('%Y-%m-%d'), 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)})
            temp_date += relativedelta(months=1); time.sleep(2)
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            # 套用新版 width='stretch'
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), width='stretch')

# --- 6. 模式 C：上櫃個股分析 (櫃買中心) ---
else:
    st.title("📉 上櫃個股分析 (TPEx 官方即時數據)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="8046")
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃分析"):
        all_tpex_data = []
        temp_date = start_month.replace(day=1)
        while temp_date <= end_date:
            roc_year = temp_date.year - 1911
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={roc_year}/{temp_date.strftime('%m')}&stk_no={stock_id}"
            data = fetch_json(url)
            if data and 'aaData' in data:
                for r in data['aaData']:
                    d_parts = r[0].split('/')
                    ad_date = datetime(int(d_parts[0])+1911, int(d_parts[1]), int(d_parts[2])).date()
                    if start_month <= ad_date <= end_date:
                        all_tpex_data.append({
                            '日期': ad_date.strftime('%Y-%m-%d'),
                            'turnover': safe_float(r[2]) * 1000, 
                            '最高': safe_float(r[4]),
                            '最低': safe_float(r[5]),
                            '收盤': safe_float(r[6]),
                            '成交量(張)': int(safe_float(r[1])/1) 
                        })
            temp_date += relativedelta(months=1); time.sleep(2)
        if all_tpex_data:
            df = pd.DataFrame(all_tpex_data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.success(f"✅ {stock_id} 上櫃數據更新完成 (來源：櫃買中心)")
            # 套用新版 width='stretch'
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), width='stretch')
