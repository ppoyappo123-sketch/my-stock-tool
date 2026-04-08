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

# --- 2. Streamlit UI ---
st.set_page_config(page_title="台股分析工具 (全能版)", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["上市個股分析 (證交所)", "櫃買綜合分析 (上櫃/興櫃/創櫃/ETF)"],
    key="nav_mode_v3"
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 3. 上市個股分析 (保持原樣) ---
if mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (證交所)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始上市分析"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr); curr += relativedelta(months=1)
        
        progress = st.progress(0)
        status = st.empty()
        for i, m in enumerate(months):
            status.write(f"📡 抓取證交所數據：{m.strftime('%Y-%m')}")
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={m.strftime('%Y%m%d')}&stockNo={stock_id}"
            res = fetch_json(url)
            if res and res.get('stat') == 'OK':
                for r in res['data']:
                    data_list.append({'日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '量(張)': int(safe_float(r[1])/1000)})
            progress.progress((i + 1) / len(months)); time.sleep(2)
        
        status.empty()
        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 4. 櫃買綜合分析 (核心修改：支援上櫃、興櫃、ETF、債券) ---
else:
    st.title("📉 櫃買中心綜合查詢")
    st.info("支援類型：上櫃、興櫃、創櫃、ETF、ETN、債券 (資料源自 TPEx)")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("代號/股票名稱", value="8046")
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始櫃買分析"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr)
            curr += relativedelta(months=1)

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, m_date in enumerate(months):
            roc_year = m_date.year - 1911
            m_str = m_date.strftime('%m')
            status_text.write(f"📡 正在從櫃買中心檢索 {stock_id}：{roc_year}/{m_str}")
            
            # --- API 策略 1：一般上櫃/ETF/債券 個股日成交資訊 ---
            tpex_url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={roc_year}/{m_str}&stk_code={stock_id}"
            res = fetch_json(tpex_url)
            
            if res and res.get('aaData'):
                for r in res['aaData']:
                    data_list.append({
                        '日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), 
                        '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '量(張)': int(safe_float(r[1].replace(',', '')))
                    })
            else:
                # --- API 策略 2：興櫃股票個股日成交資訊 (路徑不同) ---
                # 興櫃 API: tpex_url_emerging
                emerging_url = f"https://www.tpex.org.tw/web/emergingstock/historical/daily_info_result.php?l=zh-tw&d={roc_year}/{m_str}&stk_code={stock_id}"
                res_e = fetch_json(emerging_url)
                if res_e and res_e.get('aaData'):
                    for r in res_e['aaData']:
                        # 興櫃欄位索引不同：0日期, 1成交股數, 2成交金額, 4最高, 5最低, 6加權平均(代替收盤)
                        data_list.append({
                            '日期': r[0], 'turnover': safe_float(r[2]), '最高': safe_float(r[4]), 
                            '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '量(張)': int(safe_float(r[1].replace(',', ''))/1000)
                        })
            
            progress_bar.progress((i + 1) / len(months))
            time.sleep(2) 
        
        status_text.empty()

        if data_list:
            df = pd.DataFrame(data_list)
            # 指標計算
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.success(f"✅ {stock_id} 櫃買數據分析完成")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("❌ 在櫃買中心查無此資料。請確認代號是否正確（興櫃股票請輸入完整 4 或 6 碼代號）。")
