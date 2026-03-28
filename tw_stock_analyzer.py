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

# --- 2. 模擬瀏覽器 Header ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# 輔助函式：安全轉換數字 (處理逗號問題)
def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0') # 處理逗號與停券/無成交
    try:
        return float(val)
    except:
        return 0.0

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
    with st.spinner('正在與證交所連線並處理數據格式...'):
        try:
            all_data = []
            temp_date = start_date.replace(day=1)

            # --- 模式 A: 個股分析 ---
            if analysis_mode == "個股跨月分析":
                while temp_date <= end_date.replace(day=1):
                    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                    data = res.json()
                    
                    if data.get('stat') == 'OK':
                        for r in data['data']:
                            all_data.append({
                                'date': r[0], 
                                'capacity': safe_float(r[1]),
                                'turnover': safe_float(r[2]), 
                                'open': safe_float(r[3]),
                                'high': safe_float(r[4]), 
                                'low': safe_float(r[5]), 
                                'close': safe_float(r[6]),
                                'change': r[7]
                            })
                    temp_date += relativedelta(months=1)
                    time.sleep(2) 

                if not all_data:
                    st.error("❌ 抓取失敗。請檢查代號或稍後再試。")
                else:
                    df = pd.DataFrame(all_data)
                    
                    # 1. 數據換算
                    df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                    df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                    
                    # 2. 計算中間公式欄位
                    formula_label = "成交金額/(最高-最低)/1億"
                    df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['high'] - r['low'])) / 100000000 if (r['high'] - r['low']) > 0 else 0, axis=1)
                    
                    # 3. 計算指標結果 (乘回 1 億顯示小數兩位)
                    res_label = "指標結果(x1億)"
                    df[res_label] = (df[formula_label] * 100000000).round(2)
                    
                    # 4. 異常判斷
                    avg_val = df[formula_label].mean()
                    threshold = avg_val * 3
                    df['3倍異常'] = df[formula_label] > threshold

                    # ---看板呈現 (復刻圖2頂部) ---
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("區間平均指標", f"{avg_val:.10f}")
                    c2.metric("3倍異常門檻", f"{threshold:.10f}")
                    c3.metric("資料總天數", len(df))
                    st.markdown("---")

                    # --- 表格顯示 (復刻圖2排版與高亮) ---
                    # 重新命名欄位
                    df = df.rename(columns={
                        'date': '交易日期', 'open': '開盤', 'high': '最高', 
                        'low': '最低', 'close': '收盤', 'change': '漲跌'
                    })
                    
                    # 選擇顯示欄位順序 (與圖2一致)
                    display_cols = [
                        '交易日期', '開盤', '最高', '最低', '收盤', '漲跌', 
                        '成交量(張)', '成交金額(億元)', formula_label, res_label, '3倍異常'
                    ]
                    
                    # 定義異常高亮函式 (復刻圖2紅色整列)
                    def highlight_row(row):
                        return ['background-color: #fee2e2; color: #b91c1c' if row['3倍異常'] else '' for _ in row]

                    st.dataframe(
                        df[display_cols].style.apply(highlight_row, axis=1)
                        .format({
                            formula_label: '{:.10f}', # 公式顯示 10 位小數
                            res_label: '{:.2f}',
                            '成交金額(億元)': '{:.2f}',
                            '開盤': '{:.2f}', '最高': '{:.2f}', '最低': '{:.2f}', '收盤': '{:.2f}', '漲跌': '{:.2f}'
                        }),
                        use_container_width=True
                    )

            # --- 模式 B: 大盤查詢 (維持不變) ---
            else:
                while temp_date <= end_date.replace(day=1):
                    url = f"https://www.twse.com.tw/indicesReport/FMTQIK?response=json&date={temp_date.strftime('%Y%m%d')}"
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=10)
                    data = res.json()
                    if data.get('stat') == 'OK':
                        for row in data['data']:
                            all_data.append({
                                '交易日期': row[0],
                                '大盤1330金額(億)': round(safe_float(row[2]) / 100000000, 2),
                                '大盤1330量(萬張)': round(safe_float(row[1]) / 10000000, 2)
                            })
                    temp_date += relativedelta(months=1)
                    time.sleep(2)
                
                if all_data:
                    st.dataframe(pd.DataFrame(all_data), use_container_width=True)

        except Exception as e:
            st.error(f"執行失敗：{str(e)}")
