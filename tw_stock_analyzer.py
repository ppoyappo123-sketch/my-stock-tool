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
            if start_date <= date <= end_date:
                high = safe_float(quotes['high'][i])
                low = safe_float(quotes['low'][i])
                close = safe_float(quotes['close'][i])
                volume = safe_float(quotes['volume'][i])
                
                if high > 0 and low > 0:
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
    except:
        return None

# ====================== Streamlit 介面 ======================
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (Yahoo Finance)"],
    key="nav_final_v3"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 1. 大盤多日數據分析 ======================
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析 (Yahoo點數 + 證交所13:30量)")
    col1, col2 = st.columns(2)
    with col1: 
        start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=7))
    with col2: 
        end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始大盤分析"):
        all_results = []
        date_list = [start_d + timedelta(days=x) for x in range((end_d - start_d).days + 1) 
                     if (start_d + timedelta(days=x)).weekday() < 5]
        
        if date_list:
            progress = st.progress(0)
            status = st.empty()
            
            for i, d in enumerate(date_list):
                status.write(f"📡 抓取 {d.strftime('%Y-%m-%d')}")
                y = None
                try:
                    start_ts = int(time.mktime(d.timetuple()))
                    url_y = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={start_ts}&period2={start_ts + 86400}&interval=1d"
                    res_y = requests.get(url_y, headers=HEADERS, timeout=10).json()
                    result = res_y['chart']['result'][0]
                    high = result['indicators']['quote'][0]['high'][0]
                    low = result['indicators']['quote'][0]['low'][0]
                    y = {'high': round(high, 2), 'low': round(low, 2)}
                except:
                    pass
                
                v = fetch_json(f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}")
                
                if y and v and v.get('stat') == 'OK':
                    row = next((r for r in v.get('data', []) if "13:30:00" in str(r[0])), v['data'][-1] if v.get('data') else None)
                    if row:
                        score = (safe_float(row[7])/100 / (y['high'] - y['low'])) if (y['high'] - y['low']) > 0 else 0
                        all_results.append({
                            '交易日期': d.strftime('%Y-%m-%d'),
                            '加權最高': y['high'],
                            '加權最低': y['low'],
                            '13:30累積金額(百萬)': row[7],
                            formula_label: round(score, 4)
                        })
                
                progress.progress((i + 1) / len(date_list))
                time.sleep(1.5)
            
            status.empty()
            if all_results:
                df = pd.DataFrame(all_results)
                avg = df[formula_label].mean()
                df['3倍異常'] = df[formula_label] > (avg * 3)
                st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)

# ====================== 2. 上市個股分析 ======================
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE)")
    col1, col2, col3 = st.columns(3)
    with col1: 
        stock_id = st.text_input("股票代號", value="2330")
    with col2: 
        start_month = st.date_input("開始月份", value=datetime.today() - relativedelta(months=2))
    with col3: 
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 開始上市分析"):
        all_stock_data = []
        temp_date = start_month.replace(day=1)
        while temp_date <= end_date:
            url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={temp_date.strftime('%Y%m%d')}&stockNo={stock_id}"
            data = fetch_json(url)
            if data and data.get('stat') == 'OK':
                for r in data.get('data', []):
                    try:
                        d_parts = r[0].split('/')
                        ad_date = datetime(int(d_parts[0])+1911, int(d_parts[1]), int(d_parts[2])).date()
                        if start_month <= ad_date <= end_date:
                            all_stock_data.append({
                                '日期': ad_date.strftime('%Y-%m-%d'),
                                'turnover': safe_float(r[2]),
                                '最高': safe_float(r[4]),
                                '最低': safe_float(r[5]),
                                '收盤': safe_float(r[6]),
                                '成交量(張)': int(safe_float(r[1])/1000)
                            })
                    except:
                        continue
            temp_date += relativedelta(months=1)
            time.sleep(1.5)

        if all_stock_data:
            df = pd.DataFrame(all_stock_data)
            df = df.drop_duplicates(subset=['日期']).sort_values('日期')
            df[formula_label] = df.apply(
                lambda r: (r['turnover'] / (r['最高'] - r['最低'])) / 100000000 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            df['成交金額(億元)'] = (df['turnover'] / 100000000).round(2)
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
            st.success(f"✅ 上市 {stock_id} 共 {len(df)} 筆")
        else:
            st.error("❌ 沒有抓到上市資料")

# ====================== 3. 上櫃個股分析 (Yahoo Finance) ======================
else:
    st.title("📉 上櫃個股分析 (Yahoo Finance)")
    col1, col2, col3 = st.columns(3)
    with col1:
        stock_id = st.text_input("上櫃代號", value="6104")
    with col2:
        start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=45))
    with col3:
        end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始 Yahoo Finance 抓取"):
        status = st.empty()
        status.write(f"📡 正在從 Yahoo Finance 抓取 {stock_id}.TWO ...")
        
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
            st.info("建議：把開始日期改成最近 **30~60 天** 再試一次")
        
        status.empty()

st.caption("資料來源：證交所 TWSE｜Yahoo Finance | 上櫃已改用 Yahoo Finance 穩定抓取")
