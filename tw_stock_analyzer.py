import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO

# ====================== 基礎設定 ======================
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.tpex.org.tw/'
}

def fetch_text(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=25)
        if res.status_code == 200:
            return res.text
    except:
        pass
    return None

def safe_float(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').replace('"', '').strip()
    try: return float(val)
    except: return 0.0

# ====================== Streamlit ======================
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買中心)"],
    key="nav_v20"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 上櫃個股分析（pd.read_csv 智慧版） ======================
if mode == "上櫃個股分析 (櫃買中心)":
    st.title("📉 上櫃個股分析 (TPEx 櫃買中心) - 多日查詢")
    col1, col2, col3 = st.columns(3)
    with col1: 
        stock_id = st.text_input("上櫃代號", value="6104")
    with col2: 
        start_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=45))
    with col3: 
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃多日分析"):
        all_data = []
        progress = st.progress(0)
        status = st.empty()
        debug_info = []

        temp_date = start_date.replace(day=1)
        total_months = ((end_date.year - start_date.year) * 12 + end_date.month - start_date.month) + 1
        month_count = 0

        while temp_date <= end_date:
            roc_year = temp_date.year - 1911
            month_str = temp_date.strftime('%m')
            
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=csv&d={roc_year}/{month_str}&stk_no={stock_id}"
            
            status.write(f"📡 抓取 {stock_id}：{roc_year}年{month_str}月")
            csv_text = fetch_text(url)
            
            if csv_text and len(csv_text) > 10000:
                debug_info.append(f"{roc_year}/{month_str} → 抓到 {len(csv_text):,} 字元")
                try:
                    # 使用 pd.read_csv 自動解析
                    df_month = pd.read_csv(StringIO(csv_text), skiprows=1, thousands=',', encoding='utf-8-sig', on_bad_lines='skip')
                    
                    # 自動尋找包含股票代號的欄位
                    stock_col = None
                    for col in df_month.columns:
                        if df_month[col].astype(str).str.contains(stock_id, na=False).any():
                            stock_col = col
                            break
                    
                    if stock_col is not None:
                        stock_rows = df_month[df_month[stock_col].astype(str).str.contains(stock_id)]
                        for _, row in stock_rows.iterrows():
                            try:
                                # 日期通常在第一欄
                                date_str = str(row.iloc[0])
                                if '/' in date_str:
                                    y, m, d = map(int, date_str.split('/'))
                                    ad_date = datetime(y + 1911, m, d).date()
                                    
                                    if start_date <= ad_date <= end_date:
                                        all_data.append({
                                            '日期': ad_date.strftime('%Y-%m-%d'),
                                            'turnover': safe_float(row.iloc[10] if len(row) > 10 else row.iloc[-1]),
                                            '最高': safe_float(row.iloc[6] if len(row) > 6 else 0),
                                            '最低': safe_float(row.iloc[7] if len(row) > 7 else 0),
                                            '收盤': safe_float(row.iloc[3] if len(row) > 3 else 0),
                                            '成交量(張)': int(safe_float(row.iloc[9] if len(row) > 9 else 0) / 1000)
                                        })
                            except:
                                continue
                        
                        debug_info.append(f"  └─ ✅ 找到 {len(stock_rows)} 筆 {stock_id} 資料")
                    else:
                        debug_info.append(f"  └─ ⚠️ 找不到股票 {stock_id} 的欄位")
                except Exception as e:
                    debug_info.append(f"  └─ pd.read_csv 解析錯誤: {e}")
            else:
                debug_info.append(f"{roc_year}/{month_str} → 抓取失敗")

            month_count += 1
            progress.progress(month_count / total_months)
            temp_date += relativedelta(months=1)
            time.sleep(1.6)

        status.empty()

        with st.expander("🔍 抓取除錯資訊", expanded=True):
            for msg in debug_info:
                st.write(msg)

        if all_data:
            df = pd.DataFrame(all_data)
            df = df.drop_duplicates(subset=['日期']).sort_values('日期').reset_index(drop=True)
            
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            
            st.success(f"🎉 成功抓到 {len(df)} 筆資料！")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
            
            csv_download = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", csv_download, f"{stock_id}_tpex.csv", "text/csv")
        else:
            st.error("❌ 還是沒有抓到資料")
            st.info("請把開始日期改成最近30天再試一次")

st.caption("已改用 pandas 自動解析 CSV，最穩定的版本")
