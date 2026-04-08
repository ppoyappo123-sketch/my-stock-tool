import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html'
}

def fetch_text(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200:
            return res.text
    except:
        return None
    return None

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').replace('"', '').strip()
    try: return float(val)
    except: return 0.0

# ====================== 主程式 ======================
st.set_page_config(page_title="台股工具", layout="wide")
st.title("📉 上櫃個股分析 (最終正確版)")

col1, col2, col3 = st.columns(3)
with col1:
    stock_id = st.text_input("上櫃代號", value="6104")
with col2:
    start_d = st.date_input("開始日期", value=datetime(2026, 3, 1))
with col3:
    end_d = st.date_input("結束日期", value=datetime(2026, 4, 8))

if st.button("🔍 開始抓取"):
    all_data = []
    progress = st.progress(0)
    status = st.empty()

    temp_date = start_d.replace(day=1)
    total_months = ((end_d.year - start_d.year) * 12 + end_d.month - start_d.month) + 1
    month_count = 0

    while temp_date <= end_d:
        roc_year = temp_date.year - 1911
        month_str = temp_date.strftime('%m')
        
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=csv&d={roc_year}/{month_str}"
        
        status.write(f"📡 抓取 {roc_year}年{month_str}月...")
        csv_text = fetch_text(url)
        
        if csv_text:
            try:
                lines = csv_text.splitlines()
                clean_csv = "\n".join(lines[2:])   # 跳過前兩行標題
                
                df_month = pd.read_csv(StringIO(clean_csv), thousands=',', encoding='utf-8-sig', on_bad_lines='skip')
                
                # 找出真正的股票 6104（排除權證如 706104）
                stock_rows = df_month[
                    (df_month.astype(str).apply(lambda x: x.str.contains('^' + stock_id + '$', regex=True)).any(axis=1))
                ]
                
                for _, row in stock_rows.iterrows():
                    try:
                        date_str = str(row.iloc[0]).strip()
                        if '/' in date_str:
                            y, m, d = map(int, date_str.split('/'))
                            ad_date = datetime(y + 1911, m, d).date()
                            
                            if start_d <= ad_date <= end_d:
                                all_data.append({
                                    '日期': ad_date.strftime('%Y-%m-%d'),
                                    '收盤': safe_float(row.iloc[2]),   # 修正欄位
                                    '最高': safe_float(row.iloc[5]),
                                    '最低': safe_float(row.iloc[6]),
                                    '成交量(張)': int(safe_float(row.iloc[9]) / 1000),
                                    'turnover': safe_float(row.iloc[10]),
                                })
                    except:
                        continue
            except:
                pass
        
        month_count += 1
        progress.progress(month_count / total_months)
        temp_date += relativedelta(months=1)
        time.sleep(1.5)

    status.empty()

    if all_data:
        df = pd.DataFrame(all_data)
        df = df.drop_duplicates(subset=['日期']).sort_values('日期').reset_index(drop=True)
        
        formula_label = "成交金額/(最高-最低)/1億"
        df[formula_label] = df.apply(
            lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
            if (r['最高'] - r['最低']) > 0 else 0, axis=1)
        
        avg = df[formula_label].mean()
        df['3倍異常'] = df[formula_label] > (avg * 3)
        df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
        
        st.success(f"🎉 成功抓取 {len(df)} 筆資料！")
        st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載 CSV", csv, f"{stock_id}_tpex.csv", "text/csv")
    else:
        st.error("❌ 還是沒有抓到，請告訴我除錯資訊")

st.caption("已修正為實際欄位：收盤 col2, 最高 col5, 最低 col6, 成交量 col9, 金額 col10")
