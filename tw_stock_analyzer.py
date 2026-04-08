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
        # 加上隨機參數防快取
        url = f"{url}&_={int(time.time() * 1000)}"
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
st.title("📉 上櫃個股逐日分析 (精確逐日版)")

col1, col2, col3 = st.columns(3)
with col1:
    stock_id = st.text_input("上櫃代號", value="6104")
with col2:
    start_d = st.date_input("開始日期", value=datetime(2026, 3, 1))
with col3:
    end_d = st.date_input("結束日期", value=datetime(2026, 4, 8))

formula_label = "成交金額/(最高-最低)/1億"

if st.button("🔍 開始逐日抓取"):
    all_daily_data = []
    progress = st.progress(0)
    status = st.empty()

    # 產生交易日清單
    current_date = start_d
    target_dates = []
    while current_date <= end_d:
        if current_date.weekday() < 5:   # 週一到週五
            target_dates.append(current_date)
        current_date += timedelta(days=1)

    for i, date_obj in enumerate(target_dates):
        roc_year = date_obj.year - 1911
        date_str = f"{roc_year:02d}/{date_obj.month:02d}/{date_obj.day:02d}"   # 重要修正：使用完整 yyyy/mm/dd 格式

        # 正確的逐日 API
        url = (f"https://www.tpex.org.tw/web/stock/aftertrading/"
               f"daily_close_quotes/stk_quote_result.php?"
               f"l=zh-tw&o=json&d={date_str}")

        status.write(f"📡 抓取 {date_obj.strftime('%Y-%m-%d')} ...")
        
        data = fetch_json(url)
        
        if data and 'tables' in data:
            for table in data.get('tables', []):
                for row in table.get('data', []):
                    if len(row) > 10 and str(row[0]).strip() == stock_id:
                        all_daily_data.append({
                            '日期': date_obj.strftime('%Y-%m-%d'),
                            '收盤': safe_float(row[2]),
                            '最高': safe_float(row[5]),
                            '最低': safe_float(row[6]),
                            '成交量(張)': int(safe_float(row[8]) / 1000),
                            'turnover': safe_float(row[9]),      # 成交金額(元)
                        })
                        break   # 找到後跳出

        progress.progress((i + 1) / len(target_dates))
        time.sleep(1.3)   # 避免被封鎖

    status.empty()

    if all_daily_data:
        df = pd.DataFrame(all_daily_data)
        df = df.drop_duplicates(subset=['日期'])   # 去除重複
        
        df[formula_label] = df.apply(
            lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
            if (r['最高'] - r['最低']) > 0 else 0, axis=1)
        
        avg = df[formula_label].mean()
        df['3倍異常'] = df[formula_label] > (avg * 3)
        df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
        
        st.success(f"✅ 成功抓取 {len(df)} 筆不同日期資料！")
        st.dataframe(
            df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
            use_container_width=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載 CSV", csv, f"{stock_id}_daily.csv", "text/csv")
    else:
        st.error("❌ 沒有抓到任何資料，請確認日期區間或股票代號")

st.caption("逐日抓取版 | 已修正日期格式為完整年/月/日")
