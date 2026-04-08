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

def fetch_json(url, referer="https://www.google.com/"):
    """ 統一底層抓取邏輯，模擬瀏覽器行為 """
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

# --- Streamlit 介面設置 ---
st.set_page_config(page_title="台股分析工具", layout="wide")

# 側邊欄導覽
st.sidebar.header("📈 功能選單")
mode = st.sidebar.selectbox(
    "請選擇查詢項目",
    ["市場大盤走勢", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買中心)"]
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 1. 市場大盤走勢 ---
if mode == "市場大盤走勢":
    st.title("📊 市場大盤分析")
    days = st.slider("顯示最近天數", 10, 100, 30)
    
    if st.button("更新大盤數據"):
        # 上市大盤
        st.subheader("上市加權指數")
        tw_url = f"https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&_={int(time.time()*1000)}"
        tw_data = fetch_json(tw_url, "https://www.twse.com.tw/")
        if "data" in tw_data:
            df_tw = pd.DataFrame(tw_data["data"], columns=["日期", "開盤", "最高", "最低", "收盤"])
            df_tw["收盤"] = df_tw["收盤"].apply(safe_float)
            st.line_chart(df_tw.set_index("日期")["收盤"].tail(days))
            st.dataframe(df_tw.tail(15), use_container_width=True)
            
        # 上櫃大盤
        st.subheader("上櫃指數")
        tpex_url = f"https://www.tpex.org.tw/web/stock/iwd_index/index_summary/index_summary_result.php?l=zh-tw&_={int(time.time()*1000)}"
        tpex_data = fetch_json(tpex_url, "https://www.tpex.org.tw/")
        if "aaData" in tpex_data:
            df_tpex = pd.DataFrame(tpex_data["aaData"])
            df_tpex = df_tpex[[0, 1]].rename(columns={0: "日期", 1: "收盤"})
            df_tpex["收盤"] = df_tpex["收盤"].apply(safe_float)
            st.line_chart(df_tpex.set_index("日期")["收盤"].tail(days))
            st.dataframe(df_tpex.tail(15), use_container_width=True)

# --- 2. 上市個股分析 ---
elif mode == "上市個股分析 (證交所)":
    st.title("🏛️ 上市個股日成交資訊")
    col1, col2 = st.columns(2)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: query_date = st.date_input("查詢月份", value=datetime.today())

    if st.button("執行上市查詢"):
        date_str = query_date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={stock_id}"
        res = fetch_json(url, "https://www.twse.com.tw/")
        
        if "data" in res:
            df = pd.DataFrame(res["data"], columns=["日期", "成交股數", "成交金額", "開盤", "最高", "最低", "收盤", "漲跌", "成交筆數"])
            df["金額"] = df["成交金額"].apply(safe_float)
            df["最高"] = df["最高"].apply(safe_float)
            df["最低"] = df["最低"].apply(safe_float)
            
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.success(f"✅ 已取得 {stock_id} 當月數據")
            st.dataframe(df.style.apply(lambda r: ['background-color: #ffcccc' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("查無資料，請確認代號或日期。")

# --- 3. 上櫃個股分析 ---
else:
    st.title("📉 上櫃個股日成交資訊")
    col1, col2 = st.columns(2)
    with col1: stock_id = st.text_input("股票代號", value="8046")
    with col2: query_month = st.date_input("查詢月份", value=datetime.today())

    if st.button("執行上櫃查詢"):
        # 轉換民國年
        roc_year = query_month.year - 1911
        roc_date_str = f"{roc_year}/{query_month.strftime('%m')}/01"
        
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={roc_date_str}&stk_code={stock_id}"
        
        # 顯示進度
        with st.spinner('正在與櫃買中心通訊中...'):
            res = fetch_json(url, "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html")
            
        if "aaData" in res:
            # 櫃買欄位: 0日期, 1張數, 2金額, 3開盤, 4最高, 5最低, 6收盤
            df = pd.DataFrame(res["aaData"])
            df = df[[0, 2, 4, 5, 6, 1]].rename(columns={0:"日期", 2:"金額", 4:"最高", 5:"最低", 6:"收盤", 1:"張數"})
            
            for col in ["金額", "最高", "最低", "收盤", "張數"]:
                df[col] = df[col].apply(safe_float)
                
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.success(f"✅ 已取得 {stock_id} 當月數據")
            st.dataframe(df.style.apply(lambda r: ['background-color: #ffcccc' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("請求失敗或查無資料。如果持續失敗，可能是您的 IP 被櫃買中心限制，請更換網路環境。")
