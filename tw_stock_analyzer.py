import streamlit as st
import twstock
import pandas as pd
import ssl
import os
import urllib3
import requests
import time
# --- 關鍵修正：補上缺失的匯入 ---
from datetime import datetime 
from dateutil.relativedelta import relativedelta

# --- 針對雲端環境的 SSL 強化 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# 強制設定環境變數
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# 2. 頁面基礎設定
st.set_page_config(page_title="台股分析工具", layout="wide")

# 3. 側邊欄控制：切換模式
st.sidebar.header("功能設定")
analysis_mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤數據查詢"])

if analysis_mode == "個股跨月分析":
    st.title("📈 個股多月份分析 (證交所/櫃買數據)")
    stock_id = st.sidebar.text_input("股票代號", value="2330").strip()
else:
    st.title("🏛️ 大盤 13:30 成交數據查詢")
    st.info("模式：直接抓取證交所官方大盤統計 (FMTQIK)")
    stock_id = None

start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

# 4. 執行按鈕
if st.sidebar.button("🔍 執行數據分析"):
    if start_date > end_date:
        st.error("❌ 開始日期不能晚於結束日期")
    else:
        with st.spinner('正在獲取數據...'):
            try:
                all_data = []
                temp_date = start_date.replace(day=1)

                # --- 模式 A：個股分析 (維持你原本的邏輯) ---
                if analysis_mode == "個股跨月分析":
                    stock = twstock.Stock(stock_id)
                    while temp_date <= end_date.replace(day=1):
                        monthly_raw = stock.fetch(temp_date.year, temp_date.month)
                        if monthly_raw:
                            all_data.extend(monthly_raw)
                        temp_date += relativedelta(months=1)

                    if not all_data:
                        st.error("❌ 查無個股數據。")
                    else:
                        df = pd.DataFrame(all_data)
                        df['date'] = pd.to_datetime(df['date']).dt.date
                        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

                        # 核心計算
                        df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                        df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                        formula_label = "成交金額/(最高-最低)/1億"
                        
                        def calc_idx(row):
                            diff = row['high'] - row['low']
                            return (row['成交金額(億元)'] / diff) / 100000000 if diff > 0 else 0
                        
                        df[formula_label] = df.apply(calc_idx, axis=1)
                        res_label = "指標結果(x1億)"
                        df[res_label] = (df[formula_label] * 100000000).round(2)
                        
                        avg_val = df[formula_label].mean()
                        threshold = avg_val * 3
                        df['3倍異常'] = df[formula_label] > threshold

                        # 看板
                        st.markdown("---")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("區間平均指標", f"{avg_val:.10f}")
                        c2.metric("3倍異常門檻", f"{threshold:.10f}")
                        c3.metric("資料總天數", len(df))
                        st.markdown("---")

                        # 表格顯示
                        df = df.rename(columns={'date': '交易日期', 'open': '開盤', 'high': '最高', 'low': '最低', 'close': '收盤', 'change': '漲跌'})
                        display_df = df[['交易日期', '開盤', '最高', '最低', '收盤', '漲跌', '成交量(張)', '成交金額(億元)', formula_label, res_label, '3倍異常']]
                        
                        st.dataframe(
                            display_df.style.apply(lambda r: ['background-color: #fee2e2; color: #b91c1c' if r['3倍異常'] else '' for _ in r], axis=1)
                            .format({'交易日期': lambda x: x.strftime('%Y-%m-%d'), formula_label: '{:.10f}', res_label: '{:.2f}', '成交金額(億元)': '{:.2f}', '開盤': '{:.2f}', '最高': '{:.2f}', '最低': '{:.2f}', '收盤': '{:.2f}', '漲跌': '{:.2f}'}),
                            use_container_width=True
                        )
                        st.download_button("📥 下載個股報表", data=display_df.to_csv(index=False).encode('utf-8-sig'), file_name="stock_report.csv")

                # --- 模式 B：大盤查詢 (你額外要求的功能) ---
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
                                        '大盤1330成交量(萬張)': round(float(row[1].replace(',', '')) / 10000000, 2)
                                    })
                        temp_date += relativedelta(months=1)
                        time.sleep(0.5)
                    
                    if all_data:
                        m_df = pd.DataFrame(all_data)
                        st.subheader(f"📅 查詢區間：{start_date} 至 {end_date}")
                        st.dataframe(m_df, use_container_width=True)
                        st.download_button("📥 下載大盤數據", data=m_df.to_csv(index=False).encode('utf-8-sig'), file_name="market_report.csv")
                    else:
                        st.error("❌ 無法取得大盤資料。")

            except Exception as e:
                st.error(f"分析失敗：{str(e)}")
