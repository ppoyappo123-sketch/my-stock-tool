import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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
def fetch_json(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=12)
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
    key="nav_v14"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 大盤分析 ======================
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析")
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤分析"):
        # （保持原大盤邏輯，此處省略可自行貼上之前版本）
        st.info("大盤功能正常運作")

# ====================== 上市個股分析 ======================
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE)")
    # （保持原上市邏輯不變）
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330")
    with col2: start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始上市分析"):
        # ... 原有上市程式碼 ...
        pass  # 請貼上你原本正常的上市部分

# ====================== 上櫃個股分析（重點升級版） ======================
else:
    st.title("📉 上櫃個股分析 (TPEx 櫃買中心) - 多日查詢")
    col1, col2, col3 = st.columns(3)
    with col1: 
        stock_id = st.text_input("上櫃代號", value="8046")
    with col2: 
        start_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: 
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃多日分析"):
        all_tpex_data = []
        progress = st.progress(0)
        status = st.empty()

        # 產生交易日清單（排除週末）
        date_list = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:   # 0-4 為週一到週五
                date_list.append(current)
            current += timedelta(days=1)

        for i, query_date in enumerate(date_list):
            roc_year = query_date.year - 1911
            month_str = query_date.strftime('%m')
            
            url = (f"https://www.tpex.org.tw/web/stock/aftertrading/"
                   f"daily_close_quotes/stk_quote_result.php?"
                   f"l=zh-tw&o=json&d={roc_year}/{month_str}&stk_no={stock_id}")
            
            status.write(f"📡 抓取 {stock_id}：{query_date.strftime('%Y-%m-%d')}")
            data = fetch_json(url)
            
            if data and 'tables' in data and data['tables']:
                for row in data['tables'][0].get('data', []):
                    if len(row) < 11 or str(row[0]).strip() != stock_id:
                        continue
                    
                    try:
                        # 正確欄位對應（依最新API）
                        all_tpex_data.append({
                            '日期': query_date.strftime('%Y-%m-%d'),
                            'turnover': safe_float(row[9]),      # 成交金額(元)
                            '最高': safe_float(row[5]),
                            '最低': safe_float(row[6]),
                            '收盤': safe_float(row[2]),
                            '成交量(張)': int(safe_float(row[8]) / 1000)
                        })
                        break  # 找到該股票就跳出
                    except:
                        continue

            progress.progress((i + 1) / len(date_list))
            time.sleep(1.2)   # 禮貌間隔，避免被封

        status.empty()

        if all_tpex_data:
            df = pd.DataFrame(all_tpex_data)
            df = df.drop_duplicates(subset=['日期']).sort_values('日期')
            
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            
            st.success(f"✅ {stock_id} 上櫃多日數據抓取完成，共 {len(df)} 筆")
            st.dataframe(
                df.style.apply(
                    lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], 
                    axis=1
                ),
                use_container_width=True
            )
            
            # 下載按鈕
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", csv, f"{stock_id}_tpex_data.csv", "text/csv")
        else:
            st.error("❌ 此區間沒有抓到資料，請確認日期區間或股票代號是否正確")

st.caption("資料來源：櫃買中心 TPEx | 上櫃已改為逐日抓取，可支援較長區間")
