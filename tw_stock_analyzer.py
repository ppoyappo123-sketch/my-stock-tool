import streamlit as st
import pandas as pd
import requests
import time
import random
import ssl
import urllib3
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 連線基礎設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

# --- 2. 數據抓取邏輯 ---

def get_yahoo_indices(start_date, end_date):
    """ 使用 Yahoo Query API 抓取加權指數 (^TWII)，免安裝 yfinance """
    period1 = int(time.mktime(start_date.timetuple()))
    period2 = int(time.mktime((end_date + timedelta(days=1)).timetuple()))
    url = f"https://query1.finance.yahoo.com/v7/finance/download/^TWII?period1={period1}&period2={period2}&interval=1d&events=history"
    try:
        df = pd.read_csv(url)
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        return df
    except:
        return None

def fetch_twse_json(url):
    for i in range(3):
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
            if res.status_code == 200:
                data = res.json()
                if data.get('stat') == 'OK': return data
        except: pass
        time.sleep(random.uniform(3, 5))
    return None

# --- 3. Streamlit 介面 ---
st.set_page_config(page_title="台股全能分析工具", layout="wide")

st.sidebar.header("功能設定")
mode = st.sidebar.selectbox("選擇模式", ["大盤 13:30 數據", "個股多月份分析"])

start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=5))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行查詢"):
    if mode == "大盤 13:30 數據":
        st.subheader("🏛️ 大盤指數 (Yahoo) + 13:30 成交累積 (證交所)")
        yahoo_df = get_yahoo_indices(start_date, end_date)
        
        if yahoo_df is not None:
            all_data = []
            status_msg = st.empty()
            
            for index, row in yahoo_df.iterrows():
                d_str = row['Date'].replace('-', '')
                status_msg.write(f"📡 正在對接證交所數據：{row['Date']}")
                
                vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                vol_data = fetch_twse_json(vol_url)
                
                if vol_data and 'data' in vol_data:
                    # 鎖定 13:30:00 數據
                    target = next((r for r in vol_data['data'] if "13:30:00" in r[0]), None)
                    if target:
                        all_data.append({
                            '交易日期': row['Date'],
                            '加權指數最高': round(row['High'], 2),
                            '加權指數最低': round(row['Low'], 2),
                            '13:30 累積成交數量(股)': target[5],
                            '13:30 累積成交金額(百萬元)': target[6]
                        })
                time.sleep(random.uniform(2, 4))
            
            if all_data:
                status_msg.empty()
                st.dataframe(pd.DataFrame(all_data), use_container_width=True)
            else:
                st.error("無法對接證交所數據，請確認是否為交易日。")
        else:
            st.error("無法取得 Yahoo 指數數據。")

    else:
        # --- 個股分析模式 ---
        stock_id = st.sidebar.text_input("股票代號", value="2330").strip()
        st.subheader(f"📈 {stock_id} 個股多月份分析")
        all_stock_data = []
        temp_date = start_date.replace(day=1)
        
        while temp_date <= end_date.replace(day=1):
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_twse_json(url)
            if data:
                for r in data['data']:
                    all_stock_data.append({
                        '日期': r[0], 'turnover': safe_float(r[2]), 
                        '最高': safe_float(r[4]), '最低': safe_float(r[5]), 
                        '收盤': safe_float(r[6]), '成交量(張)': int(safe_float(r[1])/1000)
                    })
            temp_date += relativedelta(months=1)
            time.sleep(2)

        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            # 指標計算
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            formula_label = "成交金額/(最高-最低)/1億"
            df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.dataframe(df.style.apply(lambda row: ['background-color: #fee2e2' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
