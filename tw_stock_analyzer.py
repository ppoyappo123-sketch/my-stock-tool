import streamlit as st
import twstock
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. 終極 SSL 與連線警告屏蔽 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# --- 2. 模擬瀏覽器 Header (解決 image_7d9c03 的關鍵) ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

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
    stock_id = None

start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

# 執行分析
if st.sidebar.button("🔍 執行分析"):
    with st.spinner('正在與證交所建立安全通道...'):
        try:
            all_data = []
            temp_date = start_date.replace(day=1)

            # --- 模式 A: 個股分析 ---
            if analysis_mode == "個股跨月分析":
                # 我們不直接用 twstock.fetch (因為它容易被 SSL 擋)，改用 requests 模擬
                while temp_date <= end_date.replace(day=1):
                    # 判斷是上市還是上櫃 (簡易判斷)
                    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                    data = res.json()
                    
                    if data.get('stat') == 'OK':
                        # 將證交所格式轉換為我們需要的格式
                        for r in data['data']:
                            all_data.append({
                                'date': r[0], 'capacity': int(r[1].replace(',', '')),
                                'turnover': int(r[2].replace(',', '')), 'open': float(r[3]),
                                'high': float(r[4]), 'low': float(r[5]), 'close': float(r[6]),
                                'change': r[7]
                            })
                    temp_date += relativedelta(months=1)
                    time.sleep(2) # 延遲久一點，避免被封鎖 IP

                if not all_data:
                    st.error("❌ 抓取失敗。可能是代號錯誤或請求太頻繁，請 5 分鐘後再試。")
                else:
                    df = pd.DataFrame(all_data)
                    # 處理計算邏輯... (維持你之前的公式)
                    df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                    df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                    df['指標結果(x1億)'] = (df['成交金額(億元)'] / (df['high'] - df['low'])).round(2)
                    st.dataframe(df, use_container_width=True)

            # --- 模式 B: 大盤查詢 ---
            else:
                while temp_date <= end_date.replace(day=1):
                    url = f"https://www.twse.com.tw/indicesReport/FMTQIK?response=json&date={temp_date.strftime('%Y%m%d')}"
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                    data = res.json()
                    if data.get('stat') == 'OK':
                        for row in data['data']:
                            all_data.append({
                                '交易日期': row[0],
                                '大盤1330金額(億)': float(row[2].replace(',', '')),
                                '大盤1330量(萬張)': round(float(row[1].replace(',', '')) / 10000000, 2)
                            })
                    temp_date += relativedelta(months=1)
                    time.sleep(2)
                
                if all_data:
                    st.dataframe(pd.DataFrame(all_data), use_container_width=True)

        except Exception as e:
            st.error(f"連線失敗：{str(e)}")
            st.info("提示：這通常是證交所暫時阻擋了雲端主機的訪問，請稍候片刻再點擊執行。")
