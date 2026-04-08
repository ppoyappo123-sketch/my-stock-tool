import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import StringIO

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.tpex.org.tw/'
}

def fetch_text(url):
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=20)
        if res.status_code == 200:
            return res.text
    except:
        return None
    return None

st.set_page_config(page_title="台股工具 - 上櫃除錯版", layout="wide")

st.title("📉 上櫃個股分析 - 除錯模式")

stock_id = st.text_input("上櫃代號", value="6104")
start_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=40))
end_date = st.date_input("結束日期", value=datetime.today())

if st.button("🔍 開始抓取並顯示原始資料"):
    all_data = []
    debug_text = []
    temp_date = start_date.replace(day=1)
    
    while temp_date <= end_date:
        roc_year = temp_date.year - 1911
        month_str = temp_date.strftime('%m')
        
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=csv&d={roc_year}/{month_str}&stk_no={stock_id}"
        
        st.write(f"🔗 正在抓取: {roc_year}/{month_str} 月")
        csv_text = fetch_text(url)
        
        if csv_text:
            debug_text.append(f"✅ {roc_year}/{month_str} 抓到 {len(csv_text):,} 字元")
            
            # 顯示前 30 行原始內容（讓我們看結構）
            lines = csv_text.splitlines()[:30]
            with st.expander(f"📄 {roc_year}/{month_str} 月 前30行原始 CSV 內容", expanded=False):
                st.code("\n".join(lines), language="text")
            
            # 試著用 pandas 解析
            try:
                df_month = pd.read_csv(StringIO(csv_text), skiprows=1, on_bad_lines='skip')
                st.write(f"解析後有 {len(df_month)} 列，欄位: {list(df_month.columns)}")
                
                # 搜尋股票
                mask = df_month.astype(str).apply(lambda x: x.str.contains(stock_id, na=False)).any(axis=1)
                stock_rows = df_month[mask]
                
                if not stock_rows.empty:
                    st.success(f"找到 {len(stock_rows)} 筆 {stock_id} 資料！")
                    st.dataframe(stock_rows.head(10))
                    
                    for _, row in stock_rows.iterrows():
                        try:
                            date_str = str(row.iloc[0])
                            y, m, d = map(int, date_str.split('/'))
                            ad_date = datetime(y + 1911, m, d).date()
                            if start_date <= ad_date <= end_date:
                                all_data.append({
                                    '日期': ad_date.strftime('%Y-%m-%d'),
                                    '收盤': safe_float(row.iloc[3]),
                                    '最高': safe_float(row.iloc[6]),
                                    '最低': safe_float(row.iloc[7]),
                                    '成交量': safe_float(row.iloc[9]),
                                    '成交金額': safe_float(row.iloc[10])
                                })
                        except:
                            continue
            except Exception as e:
                debug_text.append(f"pandas 解析失敗: {e}")
        else:
            debug_text.append(f"❌ {roc_year}/{month_str} 抓取失敗")
        
        temp_date += relativedelta(months=1)
        time.sleep(1.5)

    # 最終結果
    if all_data:
        df = pd.DataFrame(all_data)
        st.success(f"🎉 總共抓到 {len(df)} 筆資料")
        st.dataframe(df)
    else:
        st.error("沒有抓到任何資料")
    
    with st.expander("全部除錯訊息"):
        for msg in debug_text:
            st.write(msg)
