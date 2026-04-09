import streamlit as st
import pandas as pd
import requests
import time
import ssl
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
    ticker = f"{stock_id}.TWO"
    start_ts = int(time.mktime(start_date.timetuple()))
    end_ts = int(time.mktime(end_date.timetuple())) + 86400
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start_ts}&period2={end_ts}&interval=1d"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=20).json()
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        
        data = []
        for i, ts in enumerate(timestamps):
            date = datetime.fromtimestamp(ts).date()
            if start_date.date() <= date <= end_date.date():
                high = safe_float(quotes['high'][i])
                low = safe_float(quotes['low'][i])
                close = safe_float(quotes['close'][i])
                volume = safe_float(quotes['volume'][i])
                
                if high > 0 and low > 0:  # 過濾無效資料
                    data.append({
                        '日期': date.strftime('%Y-%m-%d'),
                        '開盤': safe_float(quotes['open'][i]),
                        '最高': high,
                        '最低': low,
                        '收盤': close,
                        '成交量(張)': int(volume / 1000),
                        'turnover': close * volume,   # 估計成交金額
                    })
        return data
    except Exception as e:
        return None

# ====================== Streamlit ======================
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (Yahoo Finance)"],
    key="nav_yahoo_v3"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 上櫃模式 (Yahoo Finance) ======================
if mode == "上櫃個股分析 (Yahoo Finance)":
    st.title("📉 上櫃個股分析 (Yahoo Finance)")
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_id = st.text_input("上櫃代號", value="6104")
    with col2:
        start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=45))
    with col3:
        end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始 Yahoo Finance 抓取"):
        with st.spinner(f"正在從 Yahoo Finance 抓取 {stock_id}.TWO 資料..."):
            data = get_yahoo_stock_data(stock_id, start_d, end_d)
        
        if data and len(data) > 0:
            df = pd.DataFrame(data)
            df = df.sort_values('日期').reset_index(drop=True)
            
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
            st.error(f"❌ 無法抓取 {stock_id}.TWO 的資料")
            st.info("建議：\n• 把開始日期改成 **最近 30~45 天**（例如 2026/03/01 ~ 今天）\n• 確認股票代號正確\n• 稍後再試（Yahoo 有時會延遲更新）")

# ====================== 其他模式（保留原本） ======================
elif mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析")
    st.info("大盤功能維持原邏輯，請貼上你原本的大盤程式碼")

elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE)")
    st.info("上市功能維持原邏輯，請貼上你原本的上市程式碼")

st.caption("上櫃模式已改用 Yahoo Finance • 建議使用最近 1~2 個月區間")
