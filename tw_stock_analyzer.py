import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 基礎設定與 Session 模擬 ---
def get_safe_session():
    session = requests.Session()
    # 模擬瀏覽器環境
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive'
    })
    # 先連一次官網拿 Cookie
    try:
        session.get("https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html", timeout=10)
    except:
        pass
    return session

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- Streamlit 介面 ---
st.set_page_config(page_title="台股分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox("選擇模式", ["櫃買個股分析 (日成交資訊)", "上市個股分析 (證交所)"])

formula_label = "成交金額/(最高-最低)/1億"

if mode == "櫃買個股分析 (日成交資訊)":
    st.title("📉 櫃買中心個股數據")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="8046").strip()
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行數據抓取"):
        data_list = []
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr)
            curr += relativedelta(months=1)

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 建立持久化會話
        sess = get_safe_session()

        for i, m_date in enumerate(months):
            # 關鍵修正：櫃買中心 API 參數 d 雖然顯示是日期，但通常只需傳入「民國年/月」
            roc_year = m_date.year - 1911
            m_str = m_date.strftime('%m')
            # 補零並精確化日期字串 (例如 113/04/01)
            query_date = f"{roc_year}/{m_str}/01"
            
            status_text.write(f"📡 正在請求 {query_date} 數據...")
            
            # 使用正確的 RESTful API 網址
            api_url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php"
            params = {
                'l': 'zh-tw',
                'd': query_date,
                'stk_code': stock_id,
                '_': int(time.time() * 1000) # 加入時間戳防止快取
            }
            
            try:
                # 使用 params 傳遞參數比手寫 URL 更安全
                res = sess.get(api_url, params=params, timeout=15)
                
                # 檢查是否真的回傳 JSON
                if res.status_code == 200:
                    json_data = res.json()
                    if json_data.get('aaData'):
                        for r in json_data['aaData']:
                            data_list.append({
                                '日期': r[0],
                                '金額': safe_float(r[2]),
                                '最高': safe_float(r[4]),
                                '最低': safe_float(r[5]),
                                '收盤': safe_float(r[6]),
                                '張數': int(safe_float(r[1]))
                            })
                    else:
                        st.warning(f"💡 {query_date} 該月份無交易資料。")
                else:
                    st.error(f"❌ 伺服器回傳狀態碼：{res.status_code}")
                    
            except Exception as e:
                st.error(f"❌ 請求失敗: {str(e)}")

            progress_bar.progress((i + 1) / len(months))
            time.sleep(2) # 櫃買中心對頻率很敏感，建議不要低於 1.5 秒

        status_text.empty()

        if data_list:
            df = pd.DataFrame(data_list)
            # 移除可能重複的日期
            df = df.drop_duplicates(subset=['日期']).sort_values('日期')
            
            # 原始公式計算
            df[formula_label] = df.apply(lambda r: (r['金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg * 3)
            
            st.success(f"✅ 成功獲取 {len(df)} 天數據！")
            st.dataframe(df.style.apply(lambda r: ['color:red;font-weight:bold' if r['3倍異常'] else '' for _ in r], axis=1), use_container_width=True)
        else:
            st.error("😭 最終未能取得任何數據。請檢查該代號是否正確，或稍後再試。")
