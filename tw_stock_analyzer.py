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

def fetch_json(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

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

# --- 2. Streamlit UI ---
st.set_page_config(page_title="台股全方位分析工具", layout="wide")

st.sidebar.header("功能選擇")
mode = st.sidebar.selectbox("切換模式", ["大盤多日數據分析", "個股跨月異常分析"])

# 統一公式標籤
formula_label = "成交金額/(最高-最低)/1億"

if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (含指標計算)")
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤分析"):
        all_results = []
        curr_d = start_d
        date_list = [curr_d + timedelta(days=x) for x in range((end_d-start_d).days + 1) if (curr_d + timedelta(days=x)).weekday() < 5]
        
        if date_list:
            progress_bar = st.progress(0)
            for i, d in enumerate(date_list):
                y_data = get_yahoo_indices(d)
                vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}"
                vol_data = fetch_json(vol_url)
                
                if y_data and vol_data and vol_data.get('stat') == 'OK':
                    row_1330 = next((r for r in vol_data['data'] if "13:30:00" in r[0]), vol_data['data'][-1])
                    
                    # 大盤計算指標邏輯
                    # row_1330[7] 在網頁標註是百萬元，API回傳也是對應網頁數字 (如 631,122)
                    # 為了符合您的指標公式 (成交金額/1億)，這裡將百萬換算為億：金額 / 100
                    amount_in_billion = safe_float(row_1330[7]) / 100
                    high, low = y_data['high'], y_data['low']
                    score = (amount_in_billion / (high - low)) if (high - low) > 0 else 0
                    
                    all_results.append({
                        '交易日期': d.strftime('%Y-%m-%d'),
                        '加權最高': high, '加權最低': low,
                        '13:30累積金額(百萬)': row_1330[7],
                        formula_label: round(score, 4)
                    })
                progress_bar.progress((i + 1) / len(date_list))
                time.sleep(random.uniform(1.5, 3))
            
            if all_results:
                df_market = pd.DataFrame(all_results)
                avg_val = df_market[formula_label].mean()
                df_market['3倍異常'] = df_market[formula_label] > (avg_val * 3)
                st.success("✅ 大盤數據分析完成")
                st.dataframe(df_market.style.apply(lambda row: ['color: #ef4444; font-weight: bold;' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)

else:
    # --- 個股分析模式 (上市/上櫃自動切換) ---
    st.title("📈 個股跨月異常分析 (原版公式)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330").strip()
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始個股分析"):
        all_stock_data = []
        temp_date = start_month.replace(day=1)
        while temp_date <= end_date.replace(day=1):
            # 先試上市
            twse_url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_json(twse_url)
            if data and data.get('stat') == 'OK':
                for r in data['data']:
                    all_stock_data.append({'日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)})
            else:
                # 後試上櫃
                roc_year = temp_date.year - 1911
                tpex_url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={roc_year}/{temp_date.strftime('%m')}&stk_code={stock_id}"
                data = fetch_json(tpex_url)
                if data and 'aaData' in data:
                    for r in data['aaData']:
                        all_stock_data.append({'日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)})
            temp_date += relativedelta(months=1)
            time.sleep(2)
            
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.dataframe(df[['日期', '成交量(張)', '成交金額(億元)', '最高', '最低', '收盤', formula_label, '3倍異常']].style.apply(lambda row: ['color: #ef4444; font-weight: bold;' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
