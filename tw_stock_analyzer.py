import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO

# --- 基礎設定 ---
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
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# ====================== 上櫃個股分析（最新穩定版） ======================
if mode == "上櫃個股分析 (櫃買中心)":
    st.title("📉 上櫃個股分析 (TPEx 櫃買中心) - 多日查詢")
    col1, col2, col3 = st.columns(3)
    with col1: 
        stock_id = st.text_input("上櫃代號", value="8046")
    with col2: 
        start_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=45))
    with col3: 
        end_date = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 開始上櫃多日分析"):
        all_data = []
        progress = st.progress(0)
        status = st.empty()

        temp_date = start_date.replace(day=1)
        total_months = ((end_date.year - start_date.year)*12 + end_date.month - start_date.month) + 1
        month_count = 0

        while temp_date <= end_date:
            roc_year = temp_date.year - 1911
            month_str = temp_date.strftime('%m')
            
            url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=csv&d={roc_year}/{month_str}&stk_no={stock_id}"
            
            status.write(f"📡 抓取 {stock_id}：{roc_year}年{month_str}月")
            csv_text = fetch_text(url)
            
            if csv_text and len(csv_text) > 100:
                try:
                    lines = csv_text.splitlines()
                    for line in lines:
                        if not line.strip() or line.startswith('合計') or '代號' in line[:10]:
                            continue
                        
                        cols = [x.strip() for x in line.split(',')]
                        if len(cols) < 12 or cols[1] != stock_id:   # 第2欄才是股票代號
                            continue
                        
                        # 日期在第1欄 (民國年/月/日)
                        try:
                            date_str = cols[0]
                            if '/' in date_str:
                                y, m, d = map(int, date_str.split('/'))
                                ad_date = datetime(y + 1911, m, d).date()
                                
                                if start_date <= ad_date <= end_date:
                                    all_data.append({
                                        '日期': ad_date.strftime('%Y-%m-%d'),
                                        'turnover': safe_float(cols[10]),   # 成交金額(元) → 通常在第11欄 (index 10)
                                        '最高': safe_float(cols[6]),
                                        '最低': safe_float(cols[7]),
                                        '收盤': safe_float(cols[3]),
                                        '成交量(張)': int(safe_float(cols[9]) / 1000)
                                    })
                        except:
                            continue
                except Exception as e:
                    st.warning(f"解析 {roc_year}/{month_str} 時發生錯誤: {e}")
            
            month_count += 1
            progress.progress(month_count / total_months)
            temp_date += relativedelta(months=1)
            time.sleep(1.8)

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
            
            st.success(f"✅ 成功抓取 {len(df)} 筆資料")
            st.dataframe(
                df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1),
                use_container_width=True
            )
            
            csv_download = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", csv_download, f"{stock_id}_tpex.csv", "text/csv")
        else:
            st.error("❌ 還是抓不到資料")
            st.info("請嘗試以下方法：\n1. 把開始日期改成最近30天\n2. 試其他上櫃股票如 6230、6541\n3. 檢查網路或稍後再試")

else:
    st.info("請選擇「上櫃個股分析」模式測試")

st.caption("已調整為最新 CSV 欄位對應（第2欄股票代號、第1欄日期）")
