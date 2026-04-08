import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO

# ====================== 設定 ======================
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

# ====================== Streamlit ======================
st.set_page_config(page_title="台股工具", layout="wide")
st.title("📉 上櫃個股分析 (官方月資料版)")

col1, col2, col3 = st.columns(3)
with col1:
    stock_id = st.text_input("上櫃股票代號", value="6104")
with col2:
    start_d = st.date_input("開始日期", value=datetime(2026, 3, 1))
with col3:
    end_d = st.date_input("結束日期", value=datetime(2026, 4, 8))

if st.button("🔍 開始抓取一個月一次"):
    all_data = []
    progress = st.progress(0)
    status = st.empty()

    temp_date = start_d.replace(day=1)
    total_months = ((end_d.year - start_d.year) * 12 + end_d.month - start_d.month) + 1
    month_count = 0

    while temp_date <= end_d:
        roc_year = temp_date.year - 1911
        month_str = temp_date.strftime('%m')
        
        # 官方最穩定的路徑
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=csv&d={roc_year}/{month_str}"
        
        status.write(f"📡 抓取 {roc_year}年{month_str}月 全市場資料...")
        csv_text = fetch_text(url)
        
        if csv_text and len(csv_text) > 10000:
            try:
                # 解析月CSV
                df_month = pd.read_csv(StringIO(csv_text), skiprows=1, encoding='utf-8-sig', on_bad_lines='skip')
                
                # 顯示欄位幫助除錯（只顯示一次）
                if month_count == 0:
                    st.write("🔍 偵測到的欄位：", list(df_month.columns))
                
                # 過濾目標股票
                # 假設第1欄或第2欄是日期，第2欄或第1欄是股票代號
                stock_mask = False
                for col in df_month.columns[:3]:   # 只檢查前3欄
                    if df_month[col].astype(str).str.contains(stock_id).any():
                        stock_mask = df_month[col].astype(str).str.contains(stock_id)
                        break
                
                stock_df = df_month[stock_mask]
                
                for _, row in stock_df.iterrows():
                    try:
                        date_str = str(row.iloc[0]).strip()
                        if '/' in date_str:
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
                    except:
                        continue
                        
            except Exception as e:
                status.write(f"解析失敗: {e}")
        
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
        
        st.success(f"✅ 成功抓取 {len(df)} 筆資料！")
        st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載 CSV", csv, f"{stock_id}_tpex.csv", "text/csv")
    else:
        st.error("❌ 沒有抓到資料，請展開下方除錯或試其他股票")

st.caption("使用官方個股日成交資訊頁面的月CSV方式")
