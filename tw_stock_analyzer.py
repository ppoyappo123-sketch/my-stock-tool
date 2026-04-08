import streamlit as st
import pandas as pdimport streamlit as st
import pandas as pd
import urllib.request
import json
import time
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 基礎工具函數 ---
def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

def fetch_json_urllib(url, referer):
    """ 使用底層 urllib 繞過攔截 """
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        req.add_header('Referer', referer)
        req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
        
        with urllib.request.urlopen(req, timeout=15) as response:
            charset = response.info().get_content_charset() or 'utf-8'
            return json.loads(response.read().decode(charset))
    except Exception as e:
        return {"error": str(e)}

# --- Streamlit UI 設置 ---
st.set_page_config(page_title="台股全能分析系統", layout="wide")

st.sidebar.header("📊 功能導航")
mode = st.sidebar.radio(
    "請選擇功能",
    ["市場大盤分析", "櫃買個股分析 (強效版)", "上市個股分析 (證交所)"]
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 1. 市場大盤分析 ---
if mode == "市場大盤分析":
    st.title("📈 市場大盤走勢分析")
    days = st.slider("查詢天數", 10, 60, 30)
    
    if st.button("🚀 抓取大盤數據"):
        # A. 抓取上市大盤 (證交所)
        st.subheader("上市加權指數 (TWSE)")
        tw_url = f"https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&_={int(time.time()*1000)}"
        tw_data = fetch_json_urllib(tw_url, "https://www.twse.com.tw/")
        
        if "data" in tw_data:
            df_tw = pd.DataFrame(tw_data["data"], columns=["日期", "開盤", "最高", "最低", "收盤"])
            st.line_chart(df_tw.set_index("日期")["收盤"].tail(days))
            st.dataframe(df_tw.tail(10), use_container_width=True)
            
        # B. 抓取上櫃大盤 (櫃買中心)
        st.subheader("上櫃收盤指數 (TPEx)")
        tpex_index_url = f"https://www.tpex.org.tw/web/stock/iwd_index/index_summary/index_summary_result.php?l=zh-tw&_={int(time.time()*1000)}"
        tpex_data = fetch_json_urllib(tpex_index_url, "https://www.tpex.org.tw/zh-tw/mainboard/index/summary.html")
        
        if "aaData" in tpex_data:
            # 櫃買大盤欄位: 0日期, 1收盤...
            df_tpex = pd.DataFrame(tpex_data["aaData"])
            df_tpex = df_tpex[[0, 1]].rename(columns={0: "日期", 1: "收盤指數"})
            df_tpex["收盤指數"] = df_tpex["收盤指數"].apply(safe_float)
            st.line_chart(df_tpex.set_index("日期")["收盤指數"].tail(days))
            st.dataframe(df_tpex.tail(10), use_container_width=True)

# --- 2. 櫃買個股分析 ---
elif mode == "櫃買個股分析 (強效版)":
    st.title("📉 櫃買個股分析")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="8046")
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始分析"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr)
            curr += relativedelta(months=1)

        progress = st.progress(0)
        for i, m_date in enumerate(months):
            roc_year = m_date.year - 1911
            query_date = f"{roc_year}/{m_date.strftime('%m')}/01"
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={query_date}&stk_code={stock_id}"
            
            res = fetch_json_urllib(url, "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html")
            
            if "aaData" in res:
                for r in res["aaData"]:
                    data_list.append({
                        '日期': r[0], '金額': safe_float(r[2]), '最高': safe_float(r[4]),
                        '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '張數': int(safe_float(r[1]))
                    })
            time.sleep(random.uniform(2.5, 3.5))
            progress.progress((i + 1) / len(months))

        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- 3. 上市個股分析 ---
else:
    st.title("🏛️ 上市個股分析 (證交所)")
    # 此處可放您原本在證交所跑得很順的那段代碼
    st.write("請輸入證交所股票代號進行查詢。")
import urllib.request
import json
import time
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 基礎轉換函數 ---
def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- Streamlit UI ---
st.set_page_config(page_title="台股大數據分析", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox("選擇模式", ["櫃買中心數據 (強效抓取版)", "上市個股分析 (證交所)"])

formula_label = "成交金額/(最高-最低)/1億"

if mode == "櫃買中心數據 (強效抓取版)":
    st.title("📉 櫃買中心 - 個股日成交資訊")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="8046").strip()
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行強效抓取"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr)
            curr += relativedelta(months=1)

        progress = st.progress(0)
        status_msg = st.empty()

        for i, m_date in enumerate(months):
            roc_year = m_date.year - 1911
            query_date = f"{roc_year}/{m_date.strftime('%m')}/01"
            
            # 建立請求 URL
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={query_date}&stk_code={stock_id}"
            
            status_msg.write(f"📡 正在嘗試讀取：{query_date}...")
            
            try:
                # 使用 urllib 手動構造請求，避開 requests 庫的特徵
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
                req.add_header('Referer', 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html')
                req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')

                with urllib.request.urlopen(req, timeout=15) as response:
                    charset = response.info().get_content_charset() or 'utf-8'
                    raw_data = response.read().decode(charset)
                    json_data = json.loads(raw_data)
                    
                    if json_data.get('aaData'):
                        for r in json_data['aaData']:
                            data_list.append({
                                '日期': r[0], '金額': safe_float(r[2]), '最高': safe_float(r[4]),
                                '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '張數': int(safe_float(r[1]))
                            })
                    else:
                        st.warning(f"💡 {query_date} 查無資料。")
            
            except Exception as e:
                st.error(f"❌ 抓取 {query_date} 時發生錯誤: {e}")
                st.info("提示：如果持續失敗，請嘗試更換網路環境（如手機熱點）。")

            progress.progress((i + 1) / len(months))
            time.sleep(random.uniform(2.5, 3.5)) # 櫃買中心極度敏感，建議拉長間隔

        status_msg.empty()

        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            
            st.success(f"✅ 抓取成功！共 {len(df)} 筆資料。")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

else:
    st.title("🏛️ 上市分析")
    st.write("請套用您原本可執行的證交所代碼。")
