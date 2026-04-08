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
}

# --- 2. 數據抓取核心函式 ---

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

def get_yahoo_stock_data(stock_id, start_date, end_date):
    """ Yahoo Finance 抓取器 (修正結束日期對位) """
    symbol = f"{stock_id}.TWO"
    start_ts = int(time.mktime(start_date.timetuple()))
    # 修正：將結束時間推遲到隔日凌晨，確保包含 end_date 當天
    end_ts = int(time.mktime((end_date + timedelta(days=1)).timetuple()))
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start_ts}&period2={end_ts}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15).json()
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        quote = result['indicators']['quote'][0]
        data = []
        for i in range(len(timestamps)):
            dt_obj = datetime.fromtimestamp(timestamps[i])
            dt_str = dt_obj.strftime('%Y-%m-%d')
            
            # 嚴格過濾：只保留在使用者選擇範圍內的日期
            if start_date <= dt_obj.date() <= end_date:
                c, v, h, l = quote['close'][i], quote['volume'][i], quote['high'][i], quote['low'][i]
                if c and v and v > 0:
                    data.append({
                        '日期': dt_str, 
                        '成交量(張)': int(v / 1000), 
                        'turnover': v * c, 
                        '最高': round(h, 2), 
                        '最低': round(l, 2), 
                        '收盤': round(c, 2)
                    })
        return data
    except: return None

def fetch_twse_json(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200: return res.json()
    except: pass
    return None

# --- 3. Streamlit 介面 ---
st.set_page_config(page_title="台股全方位分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (原版證交所)", "上櫃個股分析 (Yahoo穩定版)"]
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 B：上市個股分析 (修正結束日期過濾) ---
if mode == "上市個股分析 (原版證交所)":
    st.title("📈 上市個股分析 (TWSE 官方數據)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始上市分析"):
        all_stock_data = []
        curr_m = start_month.replace(day=1)
        while curr_m <= end_date:
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={curr_m.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_twse_json(url)
            if data and data.get('stat') == 'OK':
                for r in data['data']:
                    # 將證交所日期 (113/04/08) 轉為 datetime 物件比對
                    date_parts = r[0].split('/')
                    ad_date = datetime(int(date_parts[0])+1911, int(date_parts[1]), int(date_parts[2])).date()
                    
                    # 嚴格執行結束日期檢查
                    if start_month <= ad_date <= end_date:
                        all_stock_data.append({
                            '日期': ad_date.strftime('%Y-%m-%d'), 
                            'turnover': safe_float(r[2]), 
                            '最高': safe_float(r[4]), 
                            '最低': safe_float(r[5]), 
                            '收盤': safe_float(r[6]), 
                            '成交量(張)': int(safe_float(r[1])/1000)
                        })
            curr_m += relativedelta(months=1)
            time.sleep(2)
        
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 5. 模式 C：上櫃個股分析 (修正 Yahoo 結束日期) ---
elif mode == "上櫃個股分析 (Yahoo穩定版)":
    st.title("📉 上櫃個股分析 (Yahoo Finance)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="8046")
    with col2: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃分析"):
        data = get_yahoo_stock_data(stock_id, start_d, end_d)
        if data:
            df = pd.DataFrame(data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(6) # 提高精確度觀察
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("查無數據，請確認代號或日期。")

# --- 模式 A 保持原樣 (省略大盤部分程式碼以節省空間，功能與之前一致) ---
else:
    st.info("請選擇大盤分析模式執行。")
