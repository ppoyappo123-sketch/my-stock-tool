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
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.twse.com.tw/zh/trading/historical/mi-5mins.html'
}

def fetch_json(url):
    for i in range(3): # 重試 3 次
        try:
            res = requests.get(url, headers=HEADERS, verify=False, timeout=30)
            if res.status_code == 200:
                content = res.json()
                if content and content.get('stat') == 'OK':
                    return content
        except Exception:
            pass
        time.sleep(random.uniform(5, 8)) # 失敗時蹲久一點再試
    return None

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').replace('+', '')
    try:
        return float(val)
    except:
        return 0.0

# 頁面配置
st.set_page_config(page_title="台股分析工具", layout="wide")

st.sidebar.header("功能設定")
analysis_mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤精確數據(13:30)"])

# 日期選擇邏輯
if analysis_mode == "個股跨月分析":
    start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
else:
    # 大盤模式預設給最近 7 天
    start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=7))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行分析"):
    with st.spinner('正在從證交所抓取數據並執行時間掃描...'):
        try:
            all_data = []
            temp_date = start_date.replace(day=1)

            # --- 模式 A: 個股分析 ---
            if analysis_mode == "個股跨月分析":
                # ... (維持之前成功的個股邏輯，此處省略以保持簡潔，請保留你原本代碼中的個股區塊) ...
                st.info("個股模式執行中...")
                pass

            # --- 模式 B: 大盤 13:30 精確數據 (含全日高低點掃描) ---
            else:
                curr_date = start_date
                while curr_date <= end_date:
                    # 排除週六日
                    if curr_date.weekday() < 5:
                        date_str = curr_date.strftime('%Y%m%d')
                        url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={date_str}"
                        
                        raw_json = fetch_json(url)
                        if raw_json and 'data' in raw_json:
                            data_list = raw_json['data']
                            
                            # --- 時間掃描器邏輯 ---
                            indices_until_1330 = []
                            target_vol_row = None
                            
                            for r in data_list:
                                # 1. 抓取成交數據 (鎖定 13:30:00)
                                if "13:30:00" in r[0]:
                                    target_vol_row = r
                                    # 注意：13:30 的指數也要算進去高低點中
                                    indices_until_1330.append(safe_float(r[1]))
                                    break
                                
                                # 2. 收集 13:30 之前所有的指數 (欄位[1]是大盤指數)
                                indices_until_1330.append(safe_float(r[1]))
                            
                            # 若沒準時 13:30:00 (通常是收盤當天無該秒)，抓最後一筆
                            if not target_vol_row:
                                target_vol_row = data_list[-1]
                            
                            # 3. 從收集到的指數中找出最高/最低點
                            day_high = max(indices_until_1330) if indices_until_1330 else 0
                            day_low = min(indices_until_1330) if indices_until_1330 else 0
                            
                            all_data.append({
                                '交易日期': curr_date.strftime('%Y-%m-%d'),
                                '13:30大盤指數': target_vol_row[1],
                                '大盤當日最高': day_high,
                                '大盤當日最低': day_low,
                                '13:30累積金額(億)': round(safe_float(target_vol_row[4]) / 100000000, 2),
                                '13:30累積量(張)': int(safe_float(target_vol_row[3]) / 1000)
                            })
                        time.sleep(random.uniform(3, 5)) # 禮貌等待防封鎖 IP
                    curr_date += timedelta(days=1)

                if all_data:
                    df = pd.DataFrame(all_data)
                    st.subheader(f"🏛️ 大盤 13:30 精確數據與全日高低點 ({start_date} ~ {end_date})")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.error("❌ 抓取失敗。請檢查日期區間是否包含交易日，或稍後再試。")

        except Exception as e:
            st.error(f"分析失敗：{str(e)}")
