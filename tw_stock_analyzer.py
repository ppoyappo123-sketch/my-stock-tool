import streamlit as st
import pandas as pd
import requests
import time
import ssl
from datetime import datetime, timedelta

# --- 1. 基礎設定 ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'Referer': 'https://www.tpex.org.tw/'
}

def fetch_json(url):
    try:
        # 加上隨機參數避免快取 (Cache) 導致數據重複
        url = f"{url}&_={int(time.time()*1000)}"
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- 2. Streamlit 介面 ---
st.set_page_config(page_title="台股逐日分析工具", layout="wide")
st.title("📉 上櫃個股逐日分析 (精確比對版)")

col1, col2, col3 = st.columns(3)
with col1: 
    stock_id = st.text_input("上櫃代號", value="6104")
with col2: 
    start_d = st.date_input("開始日期", value=datetime(2026, 4, 1))
with col3: 
    end_d = st.date_input("結束日期", value=datetime(2026, 4, 8))

formula_label = "成交金額/(最高-最低)/1億"

if st.button("🔍 開始逐日抓取"):
    all_daily_data = []
    
    # 產生日期清單
    current_date = start_d
    target_dates = []
    while current_date <= end_d:
        if current_date.weekday() < 5:
            target_dates.append(current_date)
        current_date += timedelta(days=1)
    
    if not target_dates:
        st.warning("選擇的區間內沒有交易日。")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        for i, date_obj in enumerate(target_dates):
            roc_year = date_obj.year - 1911
            date_str = f"{roc_year}/{date_obj.strftime('%m/%d')}"
            
            # 使用每日收盤行情 API
            url = (f"https://www.tpex.org.tw/web/stock/aftertrading/"
                   f"daily_close_quotes/stk_quote_result.php?"
                   f"l=zh-tw&o=json&d={date_str}")
            
            status.write(f"📡 正在抓取 {date_str} 的全市場數據...")
            data = fetch_json(url)
            
            found_today = False
            if data and 'tables' in data:
                # 遍歷所有表格，尋找含有個股資料的表格
                for table in data['tables']:
                    if found_today: break
                    for row in table.get('data', []):
                        # 精確比對代號
                        if str(row[0]).strip() == stock_id:
                            all_daily_data.append({
                                '日期': date_obj.strftime('%Y-%m-%d'),
                                '收盤': safe_float(row[2]),
                                '最高': safe_float(row[5]),
                                '最低': safe_float(row[6]),
                                '成交量(張)': int(safe_float(row[8]) / 1000),
                                'turnover': safe_float(row[9]), 
                            })
                            found_today = True
                            break
            
            progress.progress((i + 1) / len(target_dates))
            time.sleep(1.5) # 增加延遲確保櫃買中心不會回傳重複的快取資料
            
        status.empty()

        if all_daily_data:
            df = pd.DataFrame(all_daily_data)
            
            # 計算公式
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            
            st.success(f"✅ 完成！共抓取 {len(df)} 筆不重複資料。")
            st.dataframe(
                df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
                width='stretch'
            )
        else:
            st.error("❌ 抓取失敗，可能是 API 沒回傳資料或代號錯誤。")
