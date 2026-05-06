import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# 1. 基礎頁面設定
st.set_page_config(page_title="台股分析工具 (穩定輸出版)", layout="wide")

# 定義請求標頭，避免被證交所阻擋
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
}

def fetch_twse_data(date_str, stock_id):
    """ 從證交所安全抓取資料 """
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={stock_id}"
    try:
        # 使用 verify=True 確保安全性，設定 timeout 防止死當
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

# 2. UI 介面設計
st.title("📈 台股個股數據分析")
st.markdown("此版本已優化 Python 3.14 兼容性，確保數據表格穩定輸出。")

col1, col2, col3 = st.columns(3)
with col1:
    stock_id = st.text_input("股票代號", value="2330")
with col2:
    start_date = st.date_input("開始日期", value=datetime.today() - relativedelta(months=1))
with col3:
    end_date = st.date_input("結束日期", value=datetime.today())

# 3. 執行邏輯
if st.button("🚀 執行數據分析"):
    all_data = []
    current_month = start_date.replace(day=1)
    
    # 建立進度提示
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 逐月抓取
    months_to_fetch = []
    temp_m = current_month
    while temp_m <= end_date:
        months_to_fetch.append(temp_m)
        temp_m += relativedelta(months=1)
        
    for i, month_dt in enumerate(months_to_fetch):
        date_str = month_dt.strftime('%Y%m%d')
        status_text.text(f"📡 正在抓取：{month_dt.strftime('%Y-%m')} 的數據...")
        
        result = fetch_twse_data(date_str, stock_id)
        
        if result and result.get('stat') == 'OK' and 'data' in result:
            for row in result['data']:
                try:
                    # 處理民國日期： "113/05/01" -> 2024-05-01
                    date_parts = row[0].split('/')
                    ad_year = int(date_parts[0]) + 1911
                    row_date = datetime(ad_year, int(date_parts[1]), int(date_parts[2])).date()
                    
                    # 篩選在使用者選擇的範圍內
                    if start_date <= row_date <= end_date:
                        all_data.append({
                            '日期': row_date.strftime('%Y-%m-%d'),
                            '最高': float(row[4].replace(',', '')),
                            '最低': float(row[5].replace(',', '')),
                            '收盤': float(row[6].replace(',', '')),
                            '金額(億)': round(float(row[2].replace(',', '')) / 100000000, 2)
                        })
                except Exception:
                    continue
        
        # 更新進度條
        progress_bar.progress((i + 1) / len(months_to_fetch))
        # 證交所 API 限制：必須間隔避免被封鎖
        time.sleep(2)

    # 4. 資料顯示與標記
    status_text.empty()
    progress_bar.empty()

    if all_data:
        df = pd.DataFrame(all_data)
        # 指標公式：成交金額(億) / (最高 - 最低)
        formula_label = "成交金額/(最高-最低)/1億"
        df[formula_label] = df.apply(
            lambda r: round(r['金額(億)'] / (r['最高'] - r['最低']), 4) if (r['最高'] - r['最低']) > 0 else 0, 
            axis=1
        )
        
        # 計算此範圍的平均指標（作為 3 倍標記基準）
        avg_score = df[formula_label].mean()
        st.success(f"✅ 資料抓取成功！區間平均指標：{avg_score:.4f}")
        
        # 套用紅字粗體標記邏輯
        def highlight_extreme(row):
            is_extreme = row[formula_label] > (avg_score * 3)
            return ['color: red; font-weight: bold' if is_extreme else '' for _ in row]

        st.dataframe(
            df.style.apply(highlight_extreme, axis=1),
            use_container_width=True
        )
    else:
        st.error("❌ 抓取失敗。可能是代號錯誤、日期範圍無數據，或短時間內請求過於頻繁。")
