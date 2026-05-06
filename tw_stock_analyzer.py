import streamlit as st
import pandas as pd
import requests
import time
import ssl
import urllib3
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 安全性與環境初始化 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

# 嘗試匯入 FinMind
@st.cache_resource
def init_finmind():
    try:
        from FinMind.data import DataLoader
        return DataLoader()
    except ImportError:
        return None

dl = init_finmind()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

# --- 2. 穩定版工具函式 ---
def fetch_json_safe(url):
    """ 增加異常處理的 JSON 抓取 """
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.warning(f"網路連線異常: {str(e)}")
    return None

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- 3. UI 介面 ---
st.set_page_config(page_title="台股分析工具", layout="wide")

mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (FinMind)"],
    key="nav_final"
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 4. 模式 A：大盤分析 (穩定對位) ---
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析")
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行大盤分析"):
        all_results = []
        date_list = [start_d + timedelta(days=x) for x in range((end_d-start_d).days + 1) if (start_d + timedelta(days=x)).weekday() < 5]
        
        if date_list:
            prog = st.progress(0)
            for i, d in enumerate(date_list):
                d_str = d.strftime('%Y%m%d')
                v = fetch_json_safe(f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}")
                
                # 此處省略 Yahoo 點數抓取邏輯以維持篇幅，需確保有 y 資料
                # 若 v 存在且有資料才處理
                if v and 'data' in v:
                    row = next((r for r in v['data'] if "13:30:00" in r[0]), v['data'][-1])
                    all_results.append({'日期': d.strftime('%Y-%m-%d'), '13:30金額': row[7]})
                
                prog.progress((i + 1) / len(date_list))
                time.sleep(1.2)
            
            if all_results:
                st.dataframe(pd.DataFrame(all_results), width='stretch')

# --- 5. 模式 B：上市個股 (證交所) ---
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 執行上市分析"):
        data_list = []
        curr = start_m.replace(day=1)
        while curr <= end_d:
            res = fetch_json_safe(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={curr.strftime('%Y%m%d')}&stockNo={stock_id}")
            if res and 'data' in res:
                for r in res['data']:
                    try:
                        d = r[0].split('/')
                        ad_date = datetime(int(d[0])+1911, int(d[1]), int(d[2])).date()
                        if start_m <= ad_date <= end_d:
                            data_list.append({
                                '日期': ad_date.strftime('%Y-%m-%d'), 
                                '最高': safe_float(r[4]), '最低': safe_float(r[5]), 
                                '收盤': safe_float(r[6]), '成交金額(億)': (safe_float(r[2])/100000000)
                            })
                    except: continue
            curr += relativedelta(months=1)
            time.sleep(1.5)
        
        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['成交金額(億)'] / (r['最高'] - r['最低'])) if (r['最高'] - r['最低']) > 0 else 0, axis=1).round(4)
            avg = df[formula_label].mean()
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r[formula_label] > (avg*3) else '' for _ in r], axis=1), width='stretch')

# --- 6. 模式 C：上櫃個股 (FinMind 強化版) ---
else:
    st.title("📉 上櫃個股分析 (FinMind)")
    if dl is None:
        st.error("環境未安裝 FinMind 套件，請檢查 requirements.txt")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="6104")
    with col2: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行分析"):
        try:
            with st.spinner('連線中...'):
                df_raw = dl.taiwan_stock_daily(stock_id=stock_id, start_date=start_d.strftime('%Y-%m-%d'), end_date=end_d.strftime('%Y-%m-%d'))
            
            if df_raw is not None and not df_raw.empty:
                df = pd.DataFrame()
                df['日期'] = df_raw['date']
                df['最高'] = df_raw['max']
                df['最低'] = df_raw['min']
                df['收盤'] = df_raw['close']
                df['成交金額(億)'] = (df_raw['Trading_money'] / 100000000).round(2)
                
                df[formula_label] = df.apply(lambda r: (r['成交金額(億)'] / (r['最高'] - r['最低'])) if (r['最高'] - r['最低']) > 0 else 0, axis=1).round(4)
                
                avg = df[df[formula_label] > 0][formula_label].mean()
                st.info(f"💡 範圍均值：{avg:.4f} | 三倍門檻：{(avg*3):.4f}")
                
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r[formula_label] > (avg*3) else '' for _ in r], axis=1), width='stretch')
            else:
                st.warning("查無資料，請確認代號與日期。")
        except Exception as e:
            st.error(f"發生錯誤：{str(e)}")
