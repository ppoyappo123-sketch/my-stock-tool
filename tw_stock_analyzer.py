import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import time
import random
from datetime import datetime, timedelta

# --- 1. 連線基礎設定 ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/zh/trading/historical/mi-5mins.html'
}

def fetch_twse_vol(date_str):
    """ 從證交所抓取 13:30 累積成交數據 """
    url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={date_str}"
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200:
            raw = res.json()
            if raw.get('stat') == 'OK':
                # 尋找 13:30:00 這一列 (索引 5:股數, 索引 6:金額)
                target = next((r for r in raw['data'] if "13:30:00" in r[0]), None)
                return target
    except:
        pass
    return None

st.set_page_config(page_title="台股混合分析工具", layout="wide")
st.title("📊 大盤數據查詢 (Yahoo 指數 + 證交所成交量)")

# 側邊欄日期設定
start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=5))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行查詢"):
    with st.spinner('正在同步 Yahoo 指數與證交所數據...'):
        try:
            # 1. 從 Yahoo Finance 抓取加權指數 (^TWII)
            # 取得比開始日期早一點的資料以確保區間完整
            twii = yf.download("^TWII", start=start_date, end=end_date + timedelta(days=1))
            
            all_data = []
            status_msg = st.empty()

            for date, row in twii.iterrows():
                d_str = date.strftime('%Y%m%d')
                display_date = date.strftime('%Y-%m-%d')
                
                status_msg.write(f"📡 正在對接證交所 13:30 數據：{display_date}")
                
                # 2. 從證交所抓取成交量
                vol_row = fetch_twse_vol(d_str)
                
                if vol_row:
                    all_data.append({
                        '交易日期': display_date,
                        'Yahoo 加權最高': round(float(row['High']), 2),
                        'Yahoo 加權最低': round(float(row['Low']), 2),
                        '13:30 累積成交數量(股)': vol_row[5],
                        '13:30 累積成交金額(百萬元)': vol_row[6]
                    })
                
                # 僅針對證交所 API 進行禮貌延遲
                time.sleep(random.uniform(3, 5))

            if all_data:
                status_msg.empty()
                df = pd.DataFrame(all_data)
                st.success("✅ 數據整合完成！")
                st.dataframe(df, use_container_width=True)
            else:
                st.error("無法取得數據。請確認日期區間為交易日，或稍後再試。")

        except Exception as e:
            st.error(f"分析失敗：{str(e)}")
