import streamlit as st
import twstock
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
# --- 關鍵修正：必須匯入這兩個，否則網頁會崩潰 ---
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 終極 SSL 繞過 (解決 image_7d989a 報錯) ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# 頁面基礎設定
st.set_page_config(page_title="台股跨月分析工具", layout="wide")

# 側邊欄：功能切換
st.sidebar.header("功能設定")
analysis_mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤數據查詢"])

if analysis_mode == "個股跨月分析":
    st.title("📈 個股多月份分析")
    stock_id = st.sidebar.text_input("股票代號", value="2330").strip()
else:
    st.title("🏛️ 大盤 13:30 成交數據查詢")
    st.info("模式：直接抓取證交所官方大盤統計")
    stock_id = None

# 日期選擇
start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

# 執行分析
if st.sidebar.button("🔍 執行分析"):
    if start_date > end_date:
        st.error("❌ 開始日期不能晚於結束日期")
    else:
        with st.spinner('連線證交所抓取數據中...'):
            try:
                all_data = []
                temp_date = start_date.replace(day=1)

                # --- 模式 A: 個股分析 ---
                if analysis_mode == "個股跨月分析":
                    stock = twstock.Stock(stock_id)
                    while temp_date <= end_date.replace(day=1):
                        monthly_raw = stock.fetch(temp_date.year, temp_date.month)
                        if monthly_raw: all_data.extend(monthly_raw)
                        temp_date += relativedelta(months=1)
                        time.sleep(0.5) # 稍微停頓防封鎖
                    
                    if not all_data:
                        st.error("❌ 查無資料，請檢查代號是否正確。")
                    else:
                        df = pd.DataFrame(all_data)
                        df['date'] = pd.to_datetime(df['date']).dt.date
                        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
                        
                        # 計算指標
                        df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                        df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                        formula_label = "成交金額/(最高-最低)/1億"
                        df[formula_label] = df.apply(lambda r: (r['turnover']/100000000 / (r['high']-r['low'])) / 100000000 if (r['high']-r['low']) > 0 else 0, axis=1)
                        res_label = "指標結果(x1億)"
                        df[res_label] = (df[formula_label] * 100000000).round(2)
                        
                        avg_val = df[formula_label].mean()
                        df['3倍異常'] = df[formula_label] > (avg_val * 3)
                        
                        df = df.rename(columns={'date': '交易日期', 'open': '開盤', 'high': '最高', 'low': '最低', 'close': '收盤', 'change': '漲跌'})
                        st.dataframe(df[['交易日期', '開盤', '最高', '最低', '收盤', '漲跌', '成交量(張)', '成交金額(億元)', formula_label, res_label, '3倍異常']]
                                     .style.apply(lambda r: ['background-color: #fee2e2; color: #b91c1c' if r['3倍異常'] else '' for _ in r], axis=1)
                                     .format({formula_label: '{:.10f}', res_label: '{:.2f}', '成交金額(億元)': '{:.2f}'}), use_container_width=True)

                # --- 模式 B: 大盤查詢 ---
                else:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    while temp_date <= end_date.replace(day=1):
                        url = f"https://www.twse.com.tw/indicesReport/FMTQIK?response=json&date={temp_date.strftime('%Y%m%d')}"
                        res = requests.get(url, headers=headers, verify=False)
                        if res.status_code == 200:
                            data = res.json()
                            if data.get('stat') == 'OK':
                                for row in data['data']:
                                    all_data.append({
                                        '交易日期': row[0],
                                        '大盤1330金額(億)': float(row[2].replace(',', '')),
                                        '大盤1330量(萬張)': round(float(row[1].replace(',', '')) / 10000000, 2)
                                    })
                        temp_date += relativedelta(months=1)
                        time.sleep(1)
                    
                    if all_data:
                        st.dataframe(pd.DataFrame(all_data), use_container_width=True)
                    else:
                        st.error("❌ 無法取得大盤資料。")

            except Exception as e:
                st.error(f"連線失敗：{str(e)}")
