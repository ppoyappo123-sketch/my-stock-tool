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

# --- 1. 連線基礎設施 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass
os.environ['CURL_CA_BUNDLE'] = ''

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.twse.com.tw/zh/trading/historical/mi-5mins.html'
}

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0')
    try: return float(val)
    except: return 0.0

st.set_page_config(page_title="台股分析工具", layout="wide")

# 側邊欄設定
st.sidebar.header("功能設定")
mode = st.sidebar.selectbox("選擇模式", ["個股跨月分析", "大盤精確數據(13:30)"])
start_date = st.sidebar.date_input("開始日期", value=datetime.today() - timedelta(days=3))
end_date = st.sidebar.date_input("結束日期", value=datetime.today())

if st.sidebar.button("🔍 執行分析"):
    all_data = []
    
    if mode == "個股跨月分析":
        stock_id = st.sidebar.text_input("代號", value="2330").strip()
        # ... (個股邏輯保持你之前成功的版本) ...
        st.info("個股模式執行中...")
        
    else:
        # --- 大盤模式：單一來源優化版 ---
        curr_date = start_date
        status_text = st.empty()
        
        while curr_date <= end_date:
            if curr_date.weekday() < 5:
                d_str = curr_date.strftime('%Y%m%d')
                status_text.text(f"📡 正在連線證交所... 嘗試抓取 {d_str}")
                
                # 只抓 MI_5MINS (這個表有時間、指數、累積量、累積金額)
                url = f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d_str}"
                
                try:
                    # 隨機延遲，模仿真人
                    time.sleep(random.uniform(4, 7))
                    res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
                    
                    if res.status_code == 200:
                        raw = res.json()
                        if raw.get('stat') == 'OK' and 'data' in raw:
                            data = raw['data']
                            
                            # 提取當日所有指數
                            indices = [safe_float(r[1]) for r in data]
                            
                            # 尋找 13:30:00 的那列
                            target = next((r for r in data if "13:30:00" in r[0]), data[-1])
                            
                            all_data.append({
                                '交易日期': curr_date.strftime('%Y-%m-%d'),
                                '當日最高指數': max(indices),
                                '當日最低指數': min(indices),
                                '13:30累積金額(億)': round(safe_float(target[4]) / 100000000, 2),
                                '13:30累積量(張)': int(safe_float(target[3]) / 1000)
                            })
                            st.write(f"✅ {d_str} 抓取成功")
                        else:
                            st.warning(f"⚠️ {d_str} 證交所回傳：{raw.get('stat', '未知錯誤')}")
                    else:
                        st.error(f"❌ {d_str} 連線失敗 (HTTP {res.status_code})")
                except Exception as e:
                    st.error(f"❌ {d_str} 發生錯誤：{str(e)}")
            
            curr_date += timedelta(days=1)

        if all_data:
            st.success("全部數據抓取完成！")
            st.dataframe(pd.DataFrame(all_data), use_container_width=True)
        else:
            st.error("😭 依舊抓不到資料。這通常是因為 Streamlit 的 IP 被證交所暫時封鎖了。")
            st.info("💡 建議方案：請將日期區間縮短到『只查 1 天』試試看。")
