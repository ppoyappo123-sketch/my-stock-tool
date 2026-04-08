import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎安全性與 Headers 設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

# 強化 Headers，模擬真實官網訪問
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.tpex.org.tw/zh-tw/mainboard/listed/company.html',
    'X-Requested-With': 'XMLHttpRequest'
}

def fetch_tpex_json(url):
    try:
        res = requests.get(url, headers=COMMON_HEADERS, verify=False, timeout=20)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error fetching: {e}")
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- 2. Streamlit UI ---
st.set_page_config(page_title="台股全能分析器", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "模式切換", 
    ["櫃買中心綜合查詢 (上櫃/興櫃/ETF)", "上市個股分析 (證交所)"],
    key="nav_v4"
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 3. 櫃買中心綜合分析 (核心修正版) ---
if mode == "櫃買中心綜合查詢 (上櫃/興櫃/ETF)":
    st.title("📉 櫃買中心全功能查詢")
    st.caption("支援範圍：上櫃股票、興櫃、創櫃、ETF、ETN、債券")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("輸入代號 (如: 8046, 6937, 006201)", value="8046").strip()
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始櫃買數據檢索"):
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
            status_text.write(f"⏳ 正在檢索 {stock_id} 於 {roc_year}年{m_str}月 的數據...")
            
            # 策略 A: 一般上櫃/ETF/債券
            url_a = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={roc_year}/{m_str}&stk_code={stock_id}"
            res_a = fetch_tpex_json(url_a)
            
            found_this_month = False
            if res_a and res_a.get('aaData'):
                for r in res_a['aaData']:
                    # 索引: 0日期, 1張數, 2金額, 4最高, 5最低, 6收盤
                    data_list.append({
                        '日期': r[0], '成交金額': safe_float(r[2]), '最高': safe_float(r[4]), 
                        '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交張數': int(safe_float(r[1]))
                    })
                found_this_month = True
            
            # 策略 B: 如果 A 沒資料，嘗試興櫃 API
            if not found_this_month:
                url_b = f"https://www.tpex.org.tw/web/emergingstock/historical/daily_info_result.php?l=zh-tw&d={roc_year}/{m_str}&stk_code={stock_id}"
                res_b = fetch_tpex_json(url_b)
                if res_b and res_b.get('aaData'):
                    for r in res_b['aaData']:
                        # 興櫃索引: 0日期, 1股數, 2金額, 4最高, 5最低, 6均價
                        data_list.append({
                            '日期': r[0], '成交金額': safe_float(r[2]), '最高': safe_float(r[4]), 
                            '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '成交張數': int(safe_float(r[1])/1000)
                        })
                    found_this_month = True
            
            progress_bar.progress((i + 1) / len(months))
            time.sleep(random.uniform(1.0, 2.0))
        
        status_text.empty()

        if data_list:
            df = pd.DataFrame(data_list)
            # 移除重複項並按日期排序
            df = df.drop_duplicates(subset=['日期']).sort_values('日期')
            
            # 指標計算
            df[formula_label] = df.apply(lambda r: (r['成交金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.success(f"📊 {stock_id} 數據抓取成功！")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error(f"❌ 無法在櫃買中心找到 {stock_id} 的資料。請確認代號是否輸入正確。")

# --- 4. 上市部分 ---
else:
    st.title("📈 上市個股分析 (證交所)")
    # (此部分保持原樣，因為證交所原本就運作正常)
    stock_id = st.text_input("上市代號", value="2330").strip()
    if st.button("開始上市分析"):
        st.write("上市分析模組運作中...")
        # 這裡放入您原本運作正常的證交所代碼即可
