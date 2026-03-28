import streamlit as st
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. SSL 與連線警告屏蔽 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').replace('+', '')
    try:
        return float(val)
    except:
        return 0.0

st.set_page_config(page_title="台股跨月分析工具", layout="wide")

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

if st.sidebar.button("🔍 執行分析"):
    with st.spinner('正在處理數據...'):
        try:
            all_data = []
            temp_date = start_date.replace(day=1)

            if analysis_mode == "個股跨月分析":
                while temp_date <= end_date.replace(day=1):
                    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                    data = res.json()
                    if data.get('stat') == 'OK':
                        for r in data['data']:
                            all_data.append({
                                '交易日期': r[0], 
                                'capacity': safe_float(r[1]),
                                'turnover': safe_float(r[2]), 
                                '開盤': safe_float(r[3]),
                                '最高': safe_float(r[4]), 
                                '最低': safe_float(r[5]), 
                                '收盤': safe_float(r[6]),
                                '漲跌': r[7] # 漲跌維持字串以保留正負號
                            })
                    temp_date += relativedelta(months=1)
                    time.sleep(2) 

                if not all_data:
                    st.error("❌ 抓取失敗。")
                else:
                    df = pd.DataFrame(all_data)
                    df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                    df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                    
                    formula_label = "成交金額/(最高-最低)/1億"
                    df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
                    
                    res_label = "指標結果(x1億)"
                    df[res_label] = (df[formula_label] * 100000000).round(2)
                    
                    avg_val = df[formula_label].mean()
                    threshold = avg_val * 3
                    df['3倍異常'] = df[formula_label] > threshold

                    # --- 看板呈現 (復刻圖2) ---
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("區間平均指標", f"{avg_val:.10f}")
                    c2.metric("3倍異常門檻", f"{threshold:.10f}")
                    c3.metric("資料總天數", len(df))
                    st.markdown("---")

                    display_cols = ['交易日期', '開盤', '最高', '最低', '收盤', '漲跌', '成交量(張)', '成交金額(億元)', formula_label, res_label, '3倍異常']
                    
                    # 修正格式化：只針對數字欄位，避開字串欄位 '漲跌'
                    st.dataframe(
                        df[display_cols].style.apply(lambda row: ['background-color: #fee2e2; color: #b91c1c' if row['3倍異常'] else '' for _ in row], axis=1)
                        .format({
                            '開盤': '{:.2f}', '最高': '{:.2f}', '最低': '{:.2f}', '收盤': '{:.2f}',
                            '成交金額(億元)': '{:.2f}', formula_label: '{:.10f}', res_label: '{:.2f}'
                        }),
                        use_container_width=True
                    )

            else: # 大盤模式
                # ... 大盤邏輯維持原樣 ...
                st.info("大盤模式執行中...")
        except Exception as e:
            st.error(f"執行失敗：{str(e)}")
