import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 基礎轉換函數 ---
def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- Streamlit UI ---
st.set_page_config(page_title="台股分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox("選擇模式", ["上櫃個股分析 (櫃買中心樣式)", "上市個股分析 (原樣)"])

formula_label = "成交金額/(最高-最低)/1億"

# --- A. 櫃買中心模式 ---
if mode == "上櫃個股分析 (櫃買中心樣式)":
    st.title("📉 櫃買中心 - 個股日成交資訊")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="8046").strip()
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行數據抓取"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr)
            curr += relativedelta(months=1)

        progress = st.progress(0)
        
        # 使用最精簡的 Headers，只保留必要的 Referer
        simple_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html'
        }

        for i, m_date in enumerate(months):
            # 關鍵：櫃買中心 API 要求的民國日期格式
            roc_year = m_date.year - 1911
            query_date = f"{roc_year}/{m_date.strftime('%m')}/01"
            
            # 直接拼接網址，像證交所那樣
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={query_date}&stk_code={stock_id}"
            
            try:
                # 不使用 Session，直接 requests.get
                res = requests.get(url, headers=simple_headers, timeout=10)
                
                # 這裡不直接用 .json()，先檢查回傳內容是否為 JSON
                if "application/json" in res.headers.get("Content-Type", ""):
                    json_data = res.json()
                    if json_data.get('aaData'):
                        for r in json_data['aaData']:
                            data_list.append({
                                '日期': r[0], '金額': safe_float(r[2]), '最高': safe_float(r[4]),
                                '最低': safe_float(r[5]), '收盤': safe_float(r[6]), '張數': int(safe_float(r[1]))
                            })
                    else:
                        st.info(f"{query_date} 無資料。")
                else:
                    st.error(f"🛑 月份 {query_date} 被櫃買中心攔截 (未回傳資料)。")
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")

            progress.progress((i + 1) / len(months))
            time.sleep(2.0) # 櫃買非常嚴格，請務必保留延遲

        if data_list:
            df = pd.DataFrame(data_list)
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            st.success("✅ 抓取成功！")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# --- B. 證交所模式 (原樣) ---
else:
    st.title("📈 證交所 - 上市個股分析")
    stock_id = st.text_input("股票代號", value="2330").strip()
    # ... (這裡保留你原本證交所那套能跑的代碼) ...
    st.info("此部分使用您原本運作正常的邏輯。")
