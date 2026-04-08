import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎安全性設定 (防止 SSL 錯誤) ---
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
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

def get_yahoo_indices(query_date):
    """ 從 Yahoo Chart API 獲取大盤高低點 """
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

# 修正 DuplicateElementId：加上唯一的 key
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "個股跨月異常分析"],
    key="nav_menu_selector" 
)

# 統一指標公式標籤
formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤多日數據分析 ---
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (Yahoo + 證交所精確對位)")
    st.markdown("分析大盤在每日 13:30 的累積成交量，並計算單位點數消耗的能量。")
    
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤分析", key="btn_market"):
        all_results = []
        curr_d = start_d
        # 過濾週末
        date_list = [curr_d + timedelta(days=x) for x in range((end_d-start_d).days + 1) if (curr_d + timedelta(days=x)).weekday() < 5]
        
        if date_list:
            progress_bar = st.progress(0)
            status_text = st.empty()
            for i, d in enumerate(date_list):
                status_text.write(f"📡 抓取大盤數據中：{d.strftime('%Y-%m-%d')}")
                y_data = get_yahoo_indices(d)
                vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}"
                vol_data = fetch_json(vol_url)
                
                if y_data and vol_data and vol_data.get('stat') == 'OK':
                    # 精確對位：抓取 13:30:00 的那一行資料
                    row_1330 = next((r for r in vol_data['data'] if "13:30:00" in r[0]), vol_data['data'][-1])
                    
                    # 計算指標：(金額/100) / (最高-最低)
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
                time.sleep(random.uniform(1.5, 2.5))
            
            status_text.empty()
            if all_results:
                df_market = pd.DataFrame(all_results)
                avg_val = df_market[formula_label].mean()
                df_market['3倍異常'] = df_market[formula_label] > (avg_val * 3)
                st.success("✅ 大盤數據分析完成")
                st.dataframe(df_market.style.apply(lambda row: ['color: #ef4444; font-weight: bold;' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
            else:
                st.error("此區間查無數據，請確認是否為開盤日。")

# --- 5. 模式 B：個股分析模式 (上市/上櫃自動切換) ---
else:
    st.title("📈 個股跨月異常分析 (支援上市/上櫃)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330").strip()
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始個股分析", key="btn_stock"):
        all_stock_data = []
        # 計算月份列表用於進度條
        months_to_fetch = []
        temp_date = start_month.replace(day=1)
        while temp_date <= end_date.replace(day=1):
            months_to_fetch.append(temp_date)
            temp_date += relativedelta(months=1)
            
        if months_to_fetch:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, target_month in enumerate(months_to_fetch):
                m_str = target_month.strftime('%Y-%m')
                status_text.write(f"📡 抓取 {stock_id} 數據中：{m_str}")
                
                # A. 先試證交所 (上市)
                twse_url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={target_month.strftime('%Y%m%d')}&stockNo={stock_id}"
                data = fetch_json(twse_url)
                
                if data and data.get('stat') == 'OK':
                    for r in data['data']:
                        all_stock_data.append({'日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)})
                else:
                    # B. 若失敗則試櫃買中心 (上櫃)
                    roc_year = target_month.year - 1911
                    tpex_url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={roc_year}/{target_month.strftime('%m')}&stk_code={stock_id}"
                    data = fetch_json(tpex_url)
                    if data and 'aaData' in data:
                        for r in data['aaData']:
                            all_stock_data.append({'日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)})
                
                progress_bar.progress((i + 1) / len(months_to_fetch))
                time.sleep(2)
            
            status_text.empty()
            
            if all_stock_data:
                df = pd.DataFrame(all_stock_data)
                # 個股公式：成交金額/(最高-最低)/1億
                df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
                avg_val = df[formula_label].mean()
                df['3倍異常'] = df[formula_label] > (avg_val * 3)
                df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                
                st.success(f"✅ {stock_id} 分析完成")
                display_cols = ['日期', '成交量(張)', '成交金額(億元)', '最高', '最低', '收盤', formula_label, '3倍異常']
                st.dataframe(df[display_cols].style.apply(lambda row: ['color: #ef4444; font-weight: bold;' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
            else:
                st.error("上市、上櫃資料庫中均查無此代號。")
