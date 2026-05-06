import streamlit as st
import pandas as pd
import requests
import time
import ssl
import urllib3
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎安全性與環境初始化 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

# 使用 cache_resource 初始化 DataLoader，並加入錯誤處理防止回傳 None
@st.cache_resource
def get_finmind_loader():
    try:
        from FinMind.data import DataLoader
        return DataLoader()
    except Exception:
        return None

dl = get_finmind_loader()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

# --- 2. 穩定版工具函式 ---
def fetch_json_safe(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
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
st.set_page_config(page_title="台股分析工具 v2026", layout="wide")

mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (FinMind)"],
    key="nav_v2026_final" 
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 (維持原邏輯) ---
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (Yahoo + 證交所)")
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始分析"):
        all_results = []
        date_list = [start_d + timedelta(days=x) for x in range((end_d-start_d).days + 1) if (start_d + timedelta(days=x)).weekday() < 5]
        if date_list:
            progress = st.progress(0); status = st.empty()
            for i, d in enumerate(date_list):
                status.write(f"📡 正在抓取：{d.strftime('%Y-%m-%d')}")
                y = get_yahoo_indices(d)
                v = fetch_json_safe(f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}")
                if y and v and v.get('stat') == 'OK' and 'data' in v:
                    row = next((r for r in v['data'] if "13:30:00" in r[0]), v['data'][-1])
                    score = (safe_float(row[7])/100 / (y['high'] - y['low'])) if (y['high'] - y['low']) > 0 else 0
                    all_results.append({'日期': d.strftime('%Y-%m-%d'), '加權最高': y['high'], '加權最低': y['low'], '13:30累積金額(百萬)': row[7], formula_label: round(score, 4)})
                progress.progress((i + 1) / len(date_list)); time.sleep(1.2)
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results); avg = df[formula_label].mean()
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r[formula_label] > (avg * 3) else '' for _ in r], axis=1), width='stretch')

# --- 5. 模式 B：上市個股分析 ---
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (精簡版)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_m = st.date_input("開始日期", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始分析"):
        data_list = []
        curr = start_m.replace(day=1)
        while curr <= end_d:
            res = fetch_json_safe(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={curr.strftime('%Y%m%d')}&stockNo={stock_id}")
            if res and res.get('stat') == 'OK' and 'data' in res:
                for r in res['data']:
                    try:
                        d = r[0].split('/')
                        ad_date = datetime(int(d[0])+1911, int(d[1]), int(d[2])).date()
                        if start_m <= ad_date <= end_d:
                            data_list.append({'日期': ad_date.strftime('%Y-%m-%d'), '成交金額(元)': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6])})
                    except: continue
            curr += relativedelta(months=1); time.sleep(1.5)
        if data_list:
            df = pd.DataFrame(data_list)
            df['成交金額(億元)'] = (df['成交金額(元)'] / 100000000).round(2)
            df[formula_label] = df.apply(lambda r: (r['成交金額(億元)'] / (r['最高'] - r['最低'])) if (r['最高'] - r['最低']) > 0 else 0, axis=1).round(4)
            avg = df[formula_label].mean()
            st.dataframe(df[['日期','最高','最低','收盤','成交金額(億元)',formula_label]].style.apply(lambda r: ['color:red;font-weight:bold' if r[formula_label] > (avg * 3) else '' for _ in r], axis=1), width='stretch')

# --- 6. 模式 C：上櫃個股分析 (針對 NoneType 報錯的關鍵修正) ---
else:
    st.title("📉 上櫃個股分析 (FinMind)")
    if dl is None:
        st.error("⚠️ 無法載入 FinMind，請確認 requirements.txt 包含 FinMind 與 tqdm。")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="6104")
    with col2: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行分析"):
        try:
            with st.spinner('連線至 FinMind 伺服器...'):
                # 核心防崩潰：確保 api 回傳值不為 None 之前，不進行任何處理
                raw_data = dl.taiwan_stock_daily(
                    stock_id=stock_id, 
                    start_date=start_d.strftime('%Y-%m-%d'), 
                    end_date=end_d.strftime('%Y-%m-%d')
                )
            
            # 關鍵修正點：檢查 raw_data 是否為 None
            if raw_data is not None and not raw_data.empty:
                df = pd.DataFrame()
                df['日期'] = raw_data['date']
                df['最高'] = raw_data['max']
                df['最低'] = raw_data['min']
                df['收盤'] = raw_data['close']
                df['成交金額(億元)'] = (raw_data['Trading_money'] / 100000000).round(2)
                
                df[formula_label] = df.apply(lambda r: (r['成交金額(億元)'] / (r['最高'] - r['最低'])) if (r['最高'] - r['最低']) > 0 else 0, axis=1).round(4)
                
                # 計算此範圍內的平均指標 (排除 0)
                valid_scores = df[df[formula_label] > 0][formula_label]
                range_avg = valid_scores.mean() if not valid_scores.empty else 0
                threshold = range_avg * 3
                
                st.info(f"📊 目前區間平均指標：{range_avg:.4f} | 三倍門檻：{threshold:.4f}")
                
                st.dataframe(
                    df[['日期','最高','最低','收盤','成交金額(億元)',formula_label]].style.apply(
                        lambda r: ['color:red;font-weight:bold' if r[formula_label] > threshold else '' for _ in r], axis=1
                    ), width='stretch'
                )
            else:
                st.warning("⚠️ 該日期區間或代號無資料，請更換代號或縮短日期範圍。")
                
        except Exception as e:
            # 攔截報錯，避免跳出紅色 Oh no 畫面
            st.error(f"❌ 數據處理發生錯誤：{str(e)}")
            st.info("💡 提示：可能是 FinMind 伺服器忙碌，請稍候再試。")
