import streamlit as st
import pandas as pd
import requests
import time
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

def get_yahoo_indices_v2(query_date):
    """ 使用 Yahoo Chart API 抓取單日高低點 (比 CSV 下載更穩定) """
    # 轉換為 Unix 時間戳
    start_ts = int(time.mktime(query_date.timetuple()))
    end_ts = start_ts + 86400 
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={start_ts}&period2={end_ts}&interval=1d"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        data = res.json()
        result = data['chart']['result'][0]
        high = result['indicators']['quote'][0]['high'][0]
        low = result['indicators']['quote'][0]['low'][0]
        return {'high': round(high, 2), 'low': round(low, 2)}
    except:
        return None

def fetch_twse_json(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get('stat') == 'OK': return data
    except:
        pass
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

# --- 2. Streamlit 介面 ---
st.set_page_config(page_title="台股混合查詢工具", layout="wide")

st.sidebar.header("功能切換")
mode = st.sidebar.selectbox("模式選擇", ["大盤單日精確查詢", "個股跨月異常分析"])

if mode == "大盤單日精確查詢":
    st.title("🏛️ 大盤單日數據 (Yahoo 指數 + 證交所成交量)")
    # 預設選昨天 (避免當天尚未收盤導致抓不到)
    query_date = st.date_input("選擇查詢日期", value=datetime.today() - timedelta(days=1))
    
    if st.button("🔍 執行查詢"):
        with st.spinner('連線中...'):
            # 1. 抓 Yahoo 加權指數
            y_data = get_yahoo_indices_v2(query_date)
            
            # 2. 抓證交所成交量
            d_str = query_date.strftime('%Y%m%d')
            vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
            vol_data = fetch_twse_json(vol_url)
            
            if y_data and vol_data:
                # 尋找 13:30:00 累積量
                target_1330 = next((r for r in vol_data['data'] if "13:30:00" in r[0]), vol_data['data'][-1])
                
                res_df = pd.DataFrame([{
                    '日期': query_date.strftime('%Y-%m-%d'),
                    '加權最高 (Yahoo)': y_data['high'],
                    '加權最低 (Yahoo)': y_data['low'],
                    '13:30 累積數量 (股)': target_1330[5],
                    '13:30 累積金額 (百萬元)': target_1330[6]
                }])
                st.success("數據獲取成功！")
                st.table(res_df)
            else:
                st.error("無法取得數據。請檢查：1.該日是否為交易日 2.證交所是否暫時封鎖 IP (請等5分鐘再試)。")

else:
    # --- 模式：個股跨月分析 (維持原本代碼) ---
    st.title("📈 個股跨月異常分析")
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_id = st.text_input("股票代號", value="2330").strip()
    with col2:
        start_date = st.date_input("開始月份", value=datetime(2025, 1, 1))
    with col3:
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始個股分析"):
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
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            formula_label = "成交金額/(最高-最低)/1億"
            df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            st.dataframe(df.style.apply(lambda row: ['background-color: #fee2e2' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)
