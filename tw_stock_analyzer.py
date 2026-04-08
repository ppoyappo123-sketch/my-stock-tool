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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'Referer': 'https://www.tpex.org.tw/'
}

def fetch_text(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200:
            return res.text
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

# ====================== Streamlit 介面 ======================
st.set_page_config(page_title="台股即時分析工具", layout="wide")
st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式",
    ["大盤多日數據分析", "上市個股分析 (證交所)", "上櫃個股分析 (櫃買中心)"],
    key="nav_v17"
)

formula_label = "成交金額/(最高-最低)/1億"

# ====================== 1. 大盤分析 ======================
if mode == "大盤多日數據分析":
    st.title("🏛️ 大盤數據分析")
    # ... (保持不變，你可以自行補上之前版本)

# ====================== 2. 上市分析 ======================
elif mode == "上市個股分析 (證交所)":
    st.title("📈 上市個股分析 (TWSE)")
    # ... (保持不變)

# ====================== 3. 上櫃分析（強化版） ======================
else:
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
            
            if csv_text:
                debug_info.append(f"{roc_year}/{month_str} → 抓到 {len(csv_text)} 字元")
                try:
                    lines = csv_text.splitlines()
                    found = 0
                    for line in lines:
                        line = line.strip()
                        if not line or '合計' in line or '代號,名稱' in line:
                            continue
                        
                        cols = [x.strip() for x in line.split(',')]
                        if len(cols) < 12:
                            continue
                        
                        # 關鍵判斷：第2欄為股票代號
                        if cols[1] == stock_id:
                            try:
                                # 第1欄日期 (民國年/月/日)
                                y, m, d = map(int, cols[0].split('/'))
                                ad_date = datetime(y + 1911, m, d).date()
                                
                                if start_date <= ad_date <= end_date:
                                    all_data.append({
                                        '日期': ad_date.strftime('%Y-%m-%d'),
                                        'turnover': safe_float(cols[10]),   # 成交金額
                                        '最高': safe_float(cols[6]),
                                        '最低': safe_float(cols[7]),
                                        '收盤': safe_float(cols[3]),
                                        '成交量(張)': int(safe_float(cols[9]) / 1000)
                                    })
                                    found += 1
                            except:
                                continue
                    if found > 0:
                        debug_info.append(f"  └─ 成功找到 {found} 筆")
                except Exception as e:
                    debug_info.append(f"  └─ 解析錯誤: {e}")
            else:
                debug_info.append(f"{roc_year}/{month_str} → 抓取失敗")

            month_count += 1
            progress.progress(month_count / total_months)
            temp_date += relativedelta(months=1)
            time.sleep(1.6)

        status.empty()

        # 顯示除錯資訊
        with st.expander("🔍 抓取過程除錯資訊"):
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
            
            st.success(f"✅ {stock_id} 成功抓取 {len(df)} 筆資料")
            st.dataframe(
                df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
                use_container_width=True
            )
            
            csv_download = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", csv_download, f"{stock_id}_tpex.csv", "text/csv")
        else:
            st.error("❌ 此區間沒有抓到資料")
            st.info("常見原因：\n• 該股票該月份無交易\n• 日期區間太新或太舊\n• 請試 **最近30天**")

st.caption("資料來源：櫃買中心 TPEx | 已加入詳細除錯資訊")
