import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# ====================== 設定 ======================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.tpex.org.tw/'
}

def fetch_json(url):
    try:
        # 強力防快取
        url = f"{url}&_={int(time.time()*1000000)}"
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

# ====================== 主介面 ======================
st.set_page_config(page_title="台股逐日分析工具", layout="wide")
st.title("📉 上櫃個股逐日分析 (最終防重複版)")

col1, col2, col3 = st.columns(3)
with col1:
    stock_id = st.text_input("上櫃代號", value="6104")
with col2:
    start_d = st.date_input("開始日期", value=datetime(2026, 3, 20))
with col3:
    end_d = st.date_input("結束日期", value=datetime(2026, 4, 8))

formula_label = "成交金額/(最高-最低)/1億"

if st.button("🔍 開始逐日抓取"):
    all_daily_data = []
    progress = st.progress(0)
    status = st.empty()

    current = start_d
    target_dates = []
    while current <= end_d:
        if current.weekday() < 5:
            target_dates.append(current)
        current += timedelta(days=1)

    for i, date_obj in enumerate(target_dates):
        roc_year = date_obj.year - 1911
        d_str = f"{roc_year:02d}/{date_obj.month:02d}/{date_obj.day:02d}"

        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=json&d={d_str}"

        status.write(f"📡 抓取 {date_obj.strftime('%Y-%m-%d')} ...")
        
        data = fetch_json(url)
        
        found = False
        if data and 'tables' in data:
            for table in data['tables']:
                for row in table.get('data', []):
                    if len(row) > 9 and str(row[0]).strip() == stock_id:
                        all_daily_data.append({
                            '日期': date_obj.strftime('%Y-%m-%d'),
                            '收盤': safe_float(row[2]),
                            '最高': safe_float(row[5]),
                            '最低': safe_float(row[6]),
                            '成交量(張)': int(safe_float(row[8]) / 1000),
                            'turnover': safe_float(row[9]),
                        })
                        found = True
                        break
                if found:
                    break

        progress.progress((i + 1) / len(target_dates))
        time.sleep(1.8)   # 拉長間隔減少被快取

    status.empty()

    if all_daily_data:
        df = pd.DataFrame(all_daily_data)
        df = df.drop_duplicates(subset=['日期']).sort_values('日期').reset_index(drop=True)
        
        df[formula_label] = df.apply(
            lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
            if (r['最高'] - r['最低']) > 0 else 0, axis=1)
        
        avg = df[formula_label].mean()
        df['3倍異常'] = df[formula_label] > (avg * 3)
        df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
        
        st.success(f"✅ 成功抓取 **{len(df)} 筆不同日期** 的資料！")
        st.dataframe(
            df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
            use_container_width=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載 CSV", csv, f"{stock_id}_tpex_daily.csv", "text/csv")
    else:
        st.error("❌ 完全沒有抓到資料")

st.caption("逐日強制版 | 已增加隨機參數 + 較長延遲")
