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

st.set_page_config(page_title="台股工具", layout="wide")
st.title("📉 上櫃個股分析 (原始資料顯示版)")

stock_id = st.text_input("上櫃代號", value="6104")
start_d = st.date_input("開始日期", value=datetime(2026, 3, 1))
end_d = st.date_input("結束日期", value=datetime(2026, 4, 8))

if st.button("🔍 開始抓取並顯示原始資料"):
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
        
        status.write(f"抓取 {roc_year}年{month_str}月...")
        csv_text = fetch_text(url)
        
        if csv_text:
            try:
                lines = csv_text.splitlines()
                clean_csv = "\n".join(lines[2:])   # 跳過標題
                
                df_month = pd.read_csv(StringIO(clean_csv), thousands=',', encoding='utf-8-sig', on_bad_lines='skip')
                
                # 找出包含 6104 的所有列
                stock_rows = df_month[df_month.astype(str).apply(lambda x: x.str.contains(stock_id)).any(axis=1)]
                
                st.subheader(f"{roc_year}/{month_str} 月 - 找到 {len(stock_rows)} 筆 {stock_id}")
                
                for idx, row in stock_rows.iterrows():
                    st.write(f"原始第 {idx} 列: {row.tolist()[:12]}")   # 顯示前12個欄位原始內容
                    
                    try:
                        date_str = str(row.iloc[0]).strip()
                        y, m, d = map(int, date_str.split('/'))
                        ad_date = datetime(y + 1911, m, d).date()
                        
                        if start_d <= ad_date <= end_d:
                            all_data.append({
                                '日期': ad_date.strftime('%Y-%m-%d'),
                                '收盤': safe_float(row.iloc[3]),
                                '最高': safe_float(row.iloc[6]),
                                '最低': safe_float(row.iloc[7]),
                                '成交量(張)': int(safe_float(row.iloc[9]) / 1000),
                                'turnover': safe_float(row.iloc[10]),
                            })
                            st.success(f"→ 成功加入日期: {ad_date}")
                    except Exception as e:
                        st.error(f"解析失敗: {e}")
            except Exception as e:
                st.error(f"月份解析失敗: {e}")
        
        month_count += 1
        progress.progress(month_count / total_months)
        temp_date += relativedelta(months=1)
        time.sleep(1.5)

    status.empty()

    if all_data:
        df = pd.DataFrame(all_data).drop_duplicates(subset=['日期']).sort_values('日期')
        st.success(f"總共成功加入 {len(df)} 筆資料")
        st.dataframe(df)
    else:
        st.error("沒有任何資料被加入")

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0
