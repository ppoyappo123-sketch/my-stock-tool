import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ====================== 基礎設定 ======================
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://finance.yahoo.com/'
}

def fetch_json(url):
    try:
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

def get_yahoo_stock_data(stock_id, start_date, end_date):
    """使用 Yahoo Finance 抓取上櫃個股歷史資料"""
    ticker = f"{stock_id}.TWO"   # 上櫃股 ticker 格式
    start_ts = int(time.mktime(start_date.timetuple()))
    end_ts = int(time.mktime(end_date.timetuple())) + 86400
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval=1d"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=15).json()
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        
        data = []
        for i, ts in enumerate(timestamps):
            date = datetime.fromtimestamp(ts).date()
            if start_date <= date <= end_date:
                data.append({
                    '日期': date.strftime('%Y-%m-%d'),
                    '開盤': safe_float(quotes['open'][i]),
                    '最高': safe_float(quotes['high'][i]),
                    '最低': safe_float(quotes['low'][i]),
                    '收盤': safe_float(quotes['close'][i]),
                    '成交量(張)': int(safe_float(quotes['volume'][i]) / 1000),
                    'turnover': safe_float(quotes['close'][i]) * safe_float(quotes['volume'][i])   # 估計成交金額
                })
        return data
    except:
        return None

# ====================== Streamlit ======================
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (Yahoo Finance)"],
    key="nav_final"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 1. 大盤模式 ======================
if mode == "大盤多日數據分析":
    # （保留你原本的大盤功能）
    st.title("🏛️ 大盤數據分析")
    # ... 你原本的大盤程式碼可貼在這裡 ...

# ====================== 2. 上市模式 ======================
elif mode == "上市個股分析 (證交所)":
    # （保留你原本的上市功能）
    st.title("📈 上市個股分析 (TWSE)")
    # ... 你原本的上市程式碼可貼在這裡 ...

# ====================== 3. 上櫃模式（改用 Yahoo Finance） ======================
else:
    st.title("📉 上櫃個股分析 (Yahoo Finance)")
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_id = st.text_input("上櫃代號", value="6104")
    with col2:
        start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=60))
    with col3:
        end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始 Yahoo Finance 抓取"):
        status = st.empty()
        status.write("📡 正在從 Yahoo Finance 抓取資料...")
        
        data = get_yahoo_stock_data(stock_id, start_d, end_d)
        
        if data:
            df = pd.DataFrame(data)
            df = df.sort_values('日期').reset_index(drop=True)
            
            # 計算公式
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(3)
            
            st.success(f"✅ {stock_id}.TWO 抓取完成，共 {len(df)} 筆資料")
            st.dataframe(
                df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
                use_container_width=True
            )
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", csv, f"{stock_id}_yahoo.csv", "text/csv")
        else:
            st.error("❌ Yahoo Finance 抓取失敗，請確認股票代號正確（例如 6104）")
        
        status.empty()

st.caption("上櫃模式已改用 Yahoo Finance（ticker 格式：XXXX.TWO）")
