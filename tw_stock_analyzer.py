import streamlit as st
import pandas as pd
import requests
import time
import ssl
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'Referer': 'https://www.tpex.org.tw/'
}

# --- 2. 核心函式 ---
def fetch_json(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def safe_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try:
        return float(val)
    except:
        return 0.0

# --- 3. Streamlit 介面 ---
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買中心)"],
    key="nav_v13"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 大盤分析 (略) ======================
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析")
    st.info("大盤功能維持原邏輯")

# ====================== 上市個股分析 (維持原樣) ======================
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE)")
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
                    try:
                        d_parts = r[0].split('/')
                        ad_date = datetime(int(d_parts[0])+1911, int(d_parts[1]), int(d_parts[2])).date()
                        if start_month <= ad_date <= end_date:
                            all_stock_data.append({
                                '日期': ad_date.strftime('%Y-%m-%d'),
                                'turnover': safe_float(r[2]),
                                '最高': safe_float(r[4]),
                                '最低': safe_float(r[5]),
                                '收盤': safe_float(r[6]),
                                '成交量(張)': int(safe_float(r[1])/1000)
                            })
                    except: continue
            temp_date += relativedelta(months=1)
            time.sleep(1.5)
        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df[formula_label] = df.apply(lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), width='stretch')

# ====================== 上櫃個股分析 (修正完畢) ======================
else:
    st.title("📉 上櫃個股分析 (TPEx 櫃買中心)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上櫃代號", value="8046")
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃分析"):
        all_tpex_data = []
        temp_date = start_month.replace(day=1)
        progress = st.progress(0)
        status = st.empty()
        
        # 計算總月份用於進度條
        total_months = ((end_date.year - start_month.year) * 12 + end_date.month - start_month.month) + 1
        month_count = 0

        while temp_date <= end_date:
            roc_year = temp_date.year - 1911
            month_str = temp_date.strftime('%m')
            
            # 使用正確的個股歷史 API (stk_quote_result)
            url = (f"https://www.tpex.org.tw/web/stock/aftertrading/"
                   f"daily_trading_info/stk_quote_result.php?"
                   f"l=zh-tw&d={roc_year}/{month_str}&stk_no={stock_id}")
            
            status.write(f"📡 抓取 {stock_id}：{roc_year}年{month_str}月 歷史數據...")
            data = fetch_json(url)
            
            if data and 'aaData' in data:
                for row in data['aaData']:
                    try:
                        # 櫃買中心日期格式為 "113/04/01"
                        d_parts = row[0].split('/')
                        ad_date = datetime(int(d_parts[0])+1911, int(d_parts[1]), int(d_parts[2])).date()
                        
                        # 嚴格篩選在使用者選擇的範圍內
                        if start_month <= ad_date <= end_date:
                            all_tpex_data.append({
                                '日期': ad_date.strftime('%Y-%m-%d'),
                                '成交量(張)': int(safe_float(row[1]) / 1000), # 原始數據是「股」
                                'turnover': safe_float(row[2]) * 1000,       # 原始數據是「千元」
                                '開盤': safe_float(row[3]),
                                '最高': safe_float(row[4]),
                                '最低': safe_float(row[5]),
                                '收盤': safe_float(row[6]),
                            })
                    except: continue

            month_count += 1
            progress.progress(min(month_count / total_months, 1.0))
            temp_date += relativedelta(months=1)
            time.sleep(2.0) # 櫃買中心 API 頻率限制較嚴格，建議設 2 秒

        status.empty()

        if all_tpex_data:
            df = pd.DataFrame(all_tpex_data)
            df = df.sort_values('日期').reset_index(drop=True)
            
            # 計算公式
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            
            st.success(f"✅ {stock_id} 分析完成，共 {len(df)} 筆交易日")
            st.dataframe(
                df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
                width='stretch'
            )
        else:
            st.error("❌ 無法取得數據。請檢查股票代號是否為「上櫃個股」，或稍後再試。")
