import streamlit as st
import pandas as pd
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
