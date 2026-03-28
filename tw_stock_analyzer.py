import streamlit as st
import twstock
import pandas as pd
import ssl
import os
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. 終極 SSL 修復：針對 image_f631b5/image_f63579 的報錯 ---
# 禁用全域 SSL 驗證
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# 設定環境變數強制跳過憑證檢查
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

# 2. 頁面基礎設定
st.set_page_config(page_title="台股跨月分析工具", layout="wide")
st.title("📈 台股多月份分析 (證交所/櫃買數據)")

# 3. 側邊欄輸入區
st.sidebar.header("查詢條件")
stock_id = st.sidebar.text_input("股票代號", value="2330").strip()
start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行跨月數據分析"):
    if start_date > end_date:
        st.error("❌ 開始日期不能晚於結束日期")
    else:
        with st.spinner(f'正在嘗試安全連線證交所抓取 {stock_id} 跨月資料...'):
            try:
                # 初始化 stock 物件
                stock = twstock.Stock(stock_id)
                all_data = []

                # 自動遍歷月份
                temp_date = start_date.replace(day=1)
                while temp_date <= end_date.replace(day=1):
                    # fetch 會直接向證交所請求資料
                    monthly_raw = stock.fetch(temp_date.year, temp_date.month)
                    if monthly_raw:
                        all_data.extend(monthly_raw)
                    temp_date += relativedelta(months=1)

                if not all_data:
                    st.error("❌ 該區間內查無官方數據，或連線被封鎖。")
                else:
                    # 轉換為 DataFrame 並裁切到精確日期範圍
                    df = pd.DataFrame(all_data)
                    df['date'] = pd.to_datetime(df['date']).dt.date
                    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

                    # --- 核心數據計算 ---
                    # A. 成交量(張)
                    df['成交量(張)'] = (df['capacity'] / 1000).astype(int)

                    # B. 成交金額(億元)
                    df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)

                    # C. 公式指標：(成交金額/價差)/1億
                    formula_label = "成交金額/(最高-最低)/1億"


                    def calc_idx(row):
                        diff = row['high'] - row['low']
                        # 防除以零處理
                        return (row['成交金額(億元)'] / diff) / 100000000 if diff > 0 else 0


                    df[formula_label] = df.apply(calc_idx, axis=1)

                    # D. 指標結果 (乘回 1 億顯示小數兩位)
                    res_label = "指標結果(x1億)"
                    df[res_label] = (df[formula_label] * 100000000).round(2)

                    # E. 異常判斷 (平均的 3 倍)
                    avg_val = df[formula_label].mean()
                    threshold = avg_val * 3
                    df['3倍異常'] = df[formula_label] > threshold

                    # --- 看板呈現 ---
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("區間平均指標", f"{avg_val:.10f}")
                    c2.metric("3倍異常門檻", f"{threshold:.10f}")
                    c3.metric("資料總天數", len(df))
                    st.markdown("---")

                    # --- 表格顯示 ---
                    df = df.rename(columns={
                        'date': '交易日期', 'open': '開盤', 'high': '最高',
                        'low': '最低', 'close': '收盤', 'change': '漲跌'
                    })

                    display_df = df[[
                        '交易日期', '開盤', '最高', '最低', '收盤', '漲跌',
                        '成交量(張)', '成交金額(億元)', formula_label, res_label, '3倍異常'
                    ]]


                    def highlight_row(row):
                        # 3倍異常標示紅色
                        return ['background-color: #fee2e2; color: #b91c1c' if row['3倍異常'] else '' for _ in row]


                    st.dataframe(
                        display_df.style.apply(highlight_row, axis=1)
                        .format({
                            '交易日期': lambda x: x.strftime('%Y-%m-%d'),
                            formula_label: '{:.10f}',  # 10位小數
                            res_label: '{:.2f}',
                            '成交金額(億元)': '{:.2f}',
                            '開盤': '{:.2f}', '最高': '{:.2f}', '最低': '{:.2f}', '收盤': '{:.2f}', '漲跌': '{:.2f}'
                        }),
                        use_container_width=True
                    )

                    st.download_button("📥 下載分析報表", data=display_df.to_csv(index=False).encode('utf-8-sig'),
                                       file_name="report.csv")

            except Exception as e:
                st.error(f"連線失敗：{str(e)}")
                st.warning(
                    "⚠️ 若仍出現 SSL 錯誤，請在您的 Terminal 執行：`pip install --upgrade certifi` 並重啟 PyCharm。")