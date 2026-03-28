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
    'Referer': 'https://www.twse.com.tw/'
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
        time.sleep(random.uniform(3, 6))
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

# 日期選擇邏輯
if analysis_mode == "個股跨月分析":
    start_date = st.sidebar.date_input("開始日期", value=datetime(2025, 1, 1))
else:
    # 大盤逐日抓取較慢，預設給最近 5 天
    start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=5))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行分析"):
    with st.spinner('正在從證交所多重來源整合數據...'):
        try:
            all_data = []
            
            if analysis_mode == "個股跨月分析":
                stock_id = st.sidebar.text_input("股票代號", value="2330", key="stock_id_input").strip()
                temp_date = start_date.replace(day=1)
                while temp_date <= end_date.replace(day=1):
                    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
                    data = fetch_json(url)
                    if data:
                        for r in data['data']:
                            all_data.append({
                                '日期': r[0], 'capacity': safe_float(r[1]), 'turnover': safe_float(r[2]), 
                                '開盤': safe_float(r[3]), '最高': safe_float(r[4]), '最低': safe_float(r[5]), 
                                '收盤': safe_float(r[6]), '漲跌': r[7]
                            })
                    temp_date += relativedelta(months=1)
                    time.sleep(random.uniform(3, 5))
                
                if all_data:
                    df = pd.DataFrame(all_data)
                    # (此處保留你之前成功的個股計算與紅字排版邏輯...)
                    df['成交量(張)'] = (df['capacity'] / 1000).astype(int)
                    df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
                    formula_label = "成交金額/(最高-最低)/1億"
                    df[formula_label] = df.apply(lambda r: (r['turnover'] / 100000000 / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
                    res_label = "指標結果(x1億)"
                    df[res_label] = (df[formula_label] * 100000000).round(2)
                    avg_val = df[formula_label].mean()
                    df['3倍異常'] = df[formula_label] > (avg_val * 3)
                    st.dataframe(df.style.apply(lambda row: ['background-color: #fee2e2' if row['3倍異常'] else '' for _ in row], axis=1), use_container_width=True)

            else:
                # --- 模式 B: 大盤 13:30 精確數據 (混合來源) ---
                curr_date = start_date
                while curr_date <= end_date:
                    if curr_date.weekday() < 5: # 跳過週末
                        d_str = curr_date.strftime('%Y%m%d')
                        
                        # 1. 抓指數 (最高/最低) - MI_5MIN_INDICES
                        idx_url = f"https://www.twse.com.tw/exchangeReport/MI_5MIN_INDICES?response=json&date={d_str}"
                        idx_json = fetch_json(idx_url)
                        
                        # 2. 抓成交量 (13:30 累積) - MI_5MINS
                        vol_url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                        vol_json = fetch_json(vol_url)
                        
                        if idx_json and vol_json and 'data' in idx_json and 'data' in vol_json:
                            # 運算最高最低指數 (r[1]是發行量加權股價指數)
                            indices = [safe_float(r[1]) for r in idx_json['data']]
                            
                            # 找出 13:30:00 的成交金額與量
                            target_vol = next((r for r in vol_json['data'] if "13:30:00" in r[0]), vol_json['data'][-1])
                            
                            all_data.append({
                                '交易日期': curr_date.strftime('%Y-%m-%d'),
                                '當日最高指數': max(indices),
                                '當日最低指數': min(indices),
                                '13:30累積金額(億)': round(safe_float(target_vol[4]) / 100000000, 2),
                                '13:30累積量(張)': int(safe_float(target_vol[3]) / 1000)
                            })
                        time.sleep(random.uniform(4, 6))
                    curr_date += timedelta(days=1)

                if all_data:
                    st.subheader(f"🏛️ 大盤 13:30 混合來源精確分析")
                    st.dataframe(pd.DataFrame(all_data), use_container_width=True)
                else:
                    st.error("查無資料，請確認是否為交易日。")

        except Exception as e:
            st.error(f"分析失敗：{str(e)}")
