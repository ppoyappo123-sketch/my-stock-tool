import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 安全性初始化 ---
try:
    import ssl
    import urllib3
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except:
    pass

dl = get_finmind_loader()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.twse.com.tw/'
}

# --- 共用工具函式 ---
def fetch_json_safe(url: str):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return data if data and data.get('stat') == 'OK' else None
    except:
        return None
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

@st.cache_data(ttl=3600)
def get_yahoo_indices(query_date):
    ts = int(time.mktime(query_date.timetuple()))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/^TWII?period1={ts}&period2={ts+86400}&interval=1d"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        result = res['chart']['result'][0]
        return {
            'high': round(result['indicators']['quote'][0]['high'][0], 2),
            'low': round(result['indicators']['quote'][0]['low'][0], 2)
        }
    except:
        return None

# --- Streamlit 設定 ---
st.set_page_config(page_title="台股分析工具 2026", layout="wide")
st.sidebar.title("🔧 分析模式")

mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (FinMind)"],
    key="main_nav"
)

formula_label = "成交金額/(高-低)/1億"

# ====================== 大盤分析 ======================
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤多日數據分析 (Yahoo + 證交所)")
    col1, col2 = st.columns(2)
    with col1:
        start_d = st.date_input("開始日期", value=datetime.today() - timedelta(days=14))
    with col2:
        end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始分析", type="primary"):
        date_list = [start_d + timedelta(days=x) for x in range((end_d - start_d).days + 1)
                     if (start_d + timedelta(days=x)).weekday() < 5]

        all_results = []
        prog = st.progress(0)
        msg = st.empty()

        for i, d in enumerate(date_list):
            msg.write(f"📡 處理中... {d.strftime('%Y-%m-%d')}")
            y = get_yahoo_indices(d)
            v = fetch_json_safe(f"https://www.twse.com.tw/exchangeReport/MI_5MINS?response=json&date={d.strftime('%Y%m%d')}")

            if y and v and 'data' in v:
                # 取 13:30 或最後一筆
                row = next((r for r in v['data'] if "13:30:00" in r[0]), v['data'][-1])
                high_low = y['high'] - y['low']
                score = (safe_float(row[7]) / 100 / high_low) if high_low > 0 else 0

                all_results.append({
                    '日期': d.strftime('%Y-%m-%d'),
                    '加權最高': y['high'],
                    '加權最低': y['low'],
                    '13:30成交金額(億)': round(safe_float(row[7])/100, 2),
                    formula_label: round(score, 4)
                })

            prog.progress((i + 1) / len(date_list))
            time.sleep(1.1)  # 禮貌延遲

        msg.empty()

        if all_results:
            df = pd.DataFrame(all_results)
            avg = df[formula_label].mean()
            st.success(f"✅ 完成！範圍平均指標：**{avg:.4f}**")
            st.dataframe(
                df.style.apply(lambda r: ['color:red; font-weight:bold' if r[formula_label] > avg*3 else '' for _ in r], axis=1),
                use_container_width=True
            )
        else:
            st.warning("無有效數據")

# ====================== 上市個股 ======================
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (證交所)")
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="2330", max_chars=6)
    with col2: start_m = st.date_input("開始日期", value=datetime.today() - relativedelta(months=3))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🚀 執行抓取", type="primary"):
        data_list = []
        curr = start_m.replace(day=1)
        prog_bar = st.progress(0)
        count = 0

        while curr <= end_d:
            res = fetch_json_safe(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={curr.strftime('%Y%m%d')}&stockNo={stock_id}")
            if res and 'data' in res:
                for r in res['data']:
                    try:
                        y, m, d = map(int, r[0].split('/'))
                        ad_date = datetime(y + 1911, m, d).date()
                        if start_m <= ad_date <= end_d:
                            high = safe_float(r[4])
                            low = safe_float(r[5])
                            amount = safe_float(r[2])
                            data_list.append({
                                '日期': ad_date.strftime('%Y-%m-%d'),
                                '最高': high,
                                '最低': low,
                                '收盤': safe_float(r[6]),
                                '成交金額(億)': round(amount / 100000000, 2),
                                formula_label: round((amount/100000000) / (high-low), 4) if high != low else 0
                            })
                    except:
                        continue
            curr += relativedelta(months=1)
            count += 1
            prog_bar.progress(min(count / 6, 1.0))  # 粗略進度
            time.sleep(1.2)

        if data_list:
            df = pd.DataFrame(data_list)
            valid = df[df[formula_label] > 0][formula_label]
            threshold = valid.mean() * 3 if not valid.empty else 0

            st.info(f"📊 平均指標：**{valid.mean():.4f}** | 三倍門檻：**{threshold:.4f}**")
            st.dataframe(
                df.style.apply(lambda r: ['color:red; font-weight:bold' if r[formula_label] > threshold else '' for _ in r], axis=1),
                use_container_width=True
            )
        else:
            st.warning("查無數據，請確認代號與區間")


