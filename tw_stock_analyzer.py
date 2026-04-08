import streamlit as st
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
            df_tw["收盤"] = df_tw["收盤"].apply(safe_float)
            st.line_chart(df_tw.set_index("日期")["收盤"].tail(days))
            st.dataframe(df_tw.tail(10), use_container_width=True)
            
        # B. 抓取上櫃大盤 (櫃買中心)
        st.subheader("上櫃收盤指數 (TPEx)")
        tpex_index_url = f"https://www.tpex.org.tw/web/stock/iwd_index/index_summary/index_summary_result.php?l=zh-tw&_={int(time.time()*1000)}"
        tpex_data = fetch_json_urllib(tpex_index_url, "https://www.tpex.org.tw/zh-tw/mainboard/index/summary.html")
        
        if "aaData" in tpex_data:
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
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("上市代號", value="2330")
    with col2: start_m = st.date_input("開始日期", value=datetime.today() - relativedelta(months=1))
    
    if st.button("🔍 執行上市分析"):
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={start_m.strftime('%Y%m%d')}&stockNo={stock_id}"
        res = fetch_json_urllib(url, "https://www.twse.com.tw/")
        if "data" in res:
            df = pd.DataFrame(res["data"], columns=["日期", "成交股數", "成交金額", "開盤", "最高", "最低", "收盤", "漲跌", "成交筆數"])
            df["金額"] = df["成交金額"].apply(safe_float)
            df["最高"] = df["最高"].apply(safe_float)
            df["最低"] = df["最低"].apply(safe_float)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            st.dataframe(df, use_container_width=True)
