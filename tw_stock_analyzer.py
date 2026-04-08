import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO

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

# --- 2. 核心函式 ---
def fetch_text(url):
    """抓取文字內容（用於 CSV）"""
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            return res.text
    except:
        pass
    return None

def fetch_json(url):
    """抓取 JSON 內容"""
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def safe_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try:
        return float(val)
    except:
        return 0.0

def get_yahoo_indices(query_date):
    start_ts = int(time.mktime(query_date.timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={start_ts}&period2={start_ts + 86400}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        result = res['chart']['result'][0]
        high = result['indicators']['quote'][0]['high'][0]
        low = result['indicators']['quote'][0]['low'][0]
        return {'high': round(high, 2), 'low': round(low, 2)}
    except:
        return None

# --- 3. Streamlit 介面 ---
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買中心)"],
    key="nav_v15"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 上櫃個股分析（穩定多日版） ======================
if mode == "上櫃個股分析 (櫃買中心)":
    st.title("📉 上櫃個股分析 (TPEx 櫃買中心) - 多日查詢")
    col1, col2, col3 = st.columns(3)
    with col1: 
        stock_id = st.text_input("上櫃代號", value="6104")
    with col2: 
        start_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=60))
    with col3: 
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃多日分析"):
        all_data = []
        progress = st.progress(0)
        status = st.empty()

        temp_date = start_date.replace(day=1)
        total_months = ((end_date.year - start_date.year) * 12 + end_date.month - start_date.month) + 1
        month_count = 0

        while temp_date <= end_date:
            roc_year = temp_date.year - 1911
            month_str = temp_date.strftime('%m')
            
            # 使用 CSV 模式（最穩定）
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=csv&d={roc_year}/{month_str}&stk_no={stock_id}"
            
            status.write(f"📡 抓取 {stock_id}：{roc_year}年{month_str}月")
            csv_text = fetch_text(url)
            
            if csv_text and len(csv_text) > 200:
                try:
                    lines = csv_text.splitlines()
                    data_start = 0
                    for i, line in enumerate(lines):
                        if '代號' in line or '名稱' in line:
                            data_start = i + 1
                            break
                    
                    for line in lines[data_start:]:
                        if not line.strip() or line.startswith('合計') or ',' not in line:
                            continue
                        cols = [x.strip() for x in line.split(',') if x.strip()]
                        if len(cols) < 11 or cols[0] != stock_id:
                            continue
                        
                        # 解析日期（TPEx CSV 第一欄通常是日期）
                        try:
                            date_part = cols[0] if '/' in cols[0] else cols[0]
                            y, m, d = map(int, date_part.split('/'))
                            ad_date = datetime(y + 1911, m, d).date()
                            
                            if start_date <= ad_date <= end_date:
                                all_data.append({
                                    '日期': ad_date.strftime('%Y-%m-%d'),
                                    'turnover': safe_float(cols[9]),   # 成交金額(元)
                                    '最高': safe_float(cols[5]),
                                    '最低': safe_float(cols[6]),
                                    '收盤': safe_float(cols[2]),
                                    '成交量(張)': int(safe_float(cols[8]) / 1000)
                                })
                        except:
                            continue
                except Exception as e:
                    status.write(f"解析錯誤: {e}")
            
            month_count += 1
            progress.progress(month_count / total_months)
            temp_date += relativedelta(months=1)
            time.sleep(1.6)

        status.empty()

        if all_data:
            df = pd.DataFrame(all_data)
            df = df.drop_duplicates(subset=['日期']).sort_values('日期').reset_index(drop=True)
            
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            
            st.success(f"✅ {stock_id} 抓取完成，共 {len(df)} 筆交易日")
            st.dataframe(
                df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
                use_container_width=True
            )
            
            csv_download = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", csv_download, f"{stock_id}_tpex.csv", "text/csv")
        else:
            st.error("❌ 這個區間沒有抓到資料，請試試最近 1~3 個月的區間")

else:
    st.title("其他功能開發中...")
    st.info("目前重點優化上櫃功能，其他模式可自行補上原本程式碼")

st.caption("資料來源：櫃買中心 TPEx | 已改用 CSV 穩定抓取多日資料")
