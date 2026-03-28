import streamlit as st
import pandas as pd
import ssl
import os
import requests
import time
import urllib3
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 基礎連線防護 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/zh/trading/historical/mi-5mins.html'
}

def fetch_json(url):
    for i in range(3):
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=30)
            if res.status_code == 200:
                content = res.json()
                if content and content.get('stat') == 'OK':
                    return content
        except:
            pass
        time.sleep(random.uniform(5, 8))
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try:
        return float(val)
    except:
        return 0.0

st.set_page_config(page_title="台股分析工具", layout="wide")

st.sidebar.header("功能設定")
analysis_mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤精確數據(13:30)"])

start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=7))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行分析"):
    with st.spinner('正在從證交所抓取每5秒統計數據...'):
        try:
            all_data = []
            
            if analysis_mode == "個股跨月分析":
                # ... (維持之前成功的個股邏輯，此處省略以保持簡潔，請保留你原本代碼中的個股區塊) ...
                pass 
            
            else:
                # --- 模式 B: 大盤每 5 秒統計 (MI_5MINS) ---
                curr_date = start_date
                while curr_date <= end_date:
                    # 排除週六日
                    if curr_date.weekday() < 5:
                        date_str = curr_date.strftime('%Y%m%d')
                        url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={date_str}"
                        
                        raw_json = fetch_json(url)
                        if raw_json and 'data' in raw_json:
                            data_list = raw_json['data']
                            
                            # 1. 找出當天最高/最低指數 (欄位[1]是大盤指數)
                            indices = [safe_float(r[1]) for r in data_list]
                            day_high = max(indices) if indices else 0
                            day_low = min(indices) if indices else 0
                            
                            # 2. 找出 13:30:00 的成交數據 (欄位[0]是時間, [3]累積成交量, [4]累積成交金額)
                            target_row = None
                            for r in data_list:
                                if "13:30:00" in r[0]:
                                    target_row = r
                                    break
                            
                            if not target_row: # 若沒準時 13:30:00，找最後一筆
                                target_row = data_list[-1]
                            
                            all_data.append({
                                '交易日期': curr_date.strftime('%Y-%m-%d'),
                                '13:30大盤指數': target_row[1],
                                '大盤最高': day_high,
                                '大盤最低': day_low,
                                '13:30成交金額(億)': round(safe_float(target_row[4]) / 100000000, 2),
                                '13:30成交量(張)': int(safe_float(target_row[3]) / 1000)
                            })
                        time.sleep(random.uniform(3, 5))
                    curr_date += timedelta(days=1)

                if all_data:
                    df = pd.DataFrame(all_data)
                    st.subheader(f"🏛️ 大盤 13:30 精確數據 (含當日高低點)")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.error("❌ 抓取失敗。請檢查日期是否為交易日，或稍後再試。")

        except Exception as e:
            st.error(f"分析失敗：{str(e)}")
