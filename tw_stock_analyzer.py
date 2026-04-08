import streamlit as st
import pandas as pd
import requests
import time
import ssl
import urllib3
from datetime import datetime, timedelta

# --- 1. 基礎安全性設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

# --- 2. 核心數據抓取函式 (Yahoo) ---

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

def get_yahoo_stock_data(stock_id, is_tpex, start_date, end_date):
    """ 從 Yahoo Finance 抓取個股歷史數據 (支援上市/上櫃) """
    # 上市補 .TW, 上櫃補 .TWO
    suffix = ".TWO" if is_tpex else ".TW"
    symbol = f"{stock_id}{suffix}"
    
    start_ts = int(time.mktime(start_date.timetuple()))
    # 結束時間設為當天 23:59:59 確保包含最後一天
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
            # Yahoo 的 API 數據有時會含空值
            c = quote['close'][i]
            v = quote['volume'][i]
            h = quote['high'][i]
            l = quote['low'][i]
            
            if c is not None and v is not None and v > 0:
                data.append({
                    '日期': dt,
                    '成交量(張)': int(v / 1000),
                    '估算金額': v * c,  # Yahoo 無直接成交金額，以 (量*收盤) 估算
                    '最高': round(h, 2),
                    '最低': round(l, 2),
                    '收盤': round(c, 2)
                })
        return data
    except:
        return None

def get_yahoo_indices(query_date):
    """ 抓取大盤當日高低點 """
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
st.set_page_config(page_title="台股 Yahoo 穩定分析版", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (Yahoo)", "上櫃個股分析 (Yahoo)"],
    key="nav_yahoo_v1"
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 (維持原邏輯：Yahoo點數 + 證交所13:30成交量) ---
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
                # 證交所 API 僅用於大盤 13:30 的累積量
                v_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}"
                try:
                    v_res = requests.get(v_url, headers=HEADERS, timeout=10).json()
                    if y and v_res.get('stat') == 'OK':
                        row = next((r for r in v_res['data'] if "13:30:00" in r[0]), v_res['data'][-1])
                        score = (safe_float(row[7])/100 / (y['high'] - y['low'])) if (y['high'] - y['low']) > 0 else 0
                        all_results.append({'交易日期': d.strftime('%Y-%m-%d'), '加權最高': y['high'], '加權最低': y['low'], '13:30累積金額(百萬)': row[7], formula_label: round(score, 4)})
                except: pass
                progress.progress((i + 1) / len(date_list)); time.sleep(1.5)
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results); avg = df[formula_label].mean(); df['3倍異常'] = df[formula_label] > (avg * 3)
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 5 & 6. 個股分析模式 (上市 & 上櫃均使用 Yahoo) ---
else:
    is_tpex = True if "上櫃" in mode else False
    st.title(f"{'📉 上櫃' if is_tpex else '📈 上市'}個股分析 (Yahoo Finance)")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="8046" if is_tpex else "2330")
    with col2: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button(f"🚀 執行 Yahoo 分析", key="btn_stock"):
        with st.spinner('正在從 Yahoo 獲取數據...'):
            data = get_yahoo_stock_data(stock_id, is_tpex, start_d, end_d)
            
        if data:
            df = pd.DataFrame(data)
            # 公式計算
            df[formula_label] = df.apply(lambda r: (r['估算金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            
            # 整理欄位
            df['成交金額(億)'] = (df['估算金額'] / 100000000).round(2)
            display_cols = ['日期', '成交量(張)', '成交金額(億)', '最高', '最低', '收盤', formula_label, '3倍異常']
            
            st.success(f"✅ {stock_id} 數據分析完成 ({'上櫃' if is_tpex else '上市'})")
            st.dataframe(df[display_cols].style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("抓取失敗，請確認代號是否正確。")
