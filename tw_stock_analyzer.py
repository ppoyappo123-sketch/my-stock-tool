import streamlit as st
import pandas as pd
import requests
import time
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 基礎設定 ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html',
    'Host': 'www.tpex.org.tw'
}

def safe_float(val):
    if isinstance(val, str):
        val = val.replace(',', '').replace('--', '0').strip()
    try: return float(val)
    except: return 0.0

# --- Streamlit 介面 ---
st.set_page_config(page_title="櫃買數據分析工具", layout="wide")

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "選擇模式", 
    ["櫃買個股分析 (日成交資訊)", "上市個股分析 (證交所)"],
    key="tpex_main_nav"
)

formula_label = "成交金額/(最高-最低)/1億"

if mode == "櫃買個股分析 (日成交資訊)":
    st.title("📉 櫃買中心個股日成交資訊")
    
    col1, col2, col3 = st.columns(3)
    with col1: stock_id = st.text_input("股票代號", value="8046").strip()
    with col2: start_m = st.date_input("開始月份", value=datetime.today() - relativedelta(months=1))
    with col3: end_d = st.date_input("結束日期", value=datetime.today())

    if st.button("🔍 執行數據抓取"):
        data_list = []
        # 生成月份清單
        curr = start_m.replace(day=1)
        months = []
        while curr <= end_d.replace(day=1):
            months.append(curr)
            curr += relativedelta(months=1)

        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, m_date in enumerate(months):
            # 轉換民國年格式：113/04/01
            roc_year = m_date.year - 1911
            # 櫃買中心此 API 必須傳入完整的民國日期字串，例如 113/04/01
            date_str = f"{roc_year}/{m_date.strftime('%m')}/01"
            
            status_text.write(f"📡 正在調用 API：{date_str} (代號: {stock_id})")
            
            # 您指定的「個股日成交資訊」精確 API 網址
            api_url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/stk_quote_result.php?l=zh-tw&d={date_str}&stk_code={stock_id}"
            
            try:
                res = requests.get(api_url, headers=HEADERS, timeout=15)
                json_data = res.json()
                
                if json_data and "aaData" in json_data and json_data["aaData"]:
                    for r in json_data["aaData"]:
                        # 櫃買中心欄位順序：
                        # 0:日期, 1:張數, 2:金額, 3:開盤, 4:最高, 5:最低, 6:收盤...
                        data_list.append({
                            '日期': r[0],
                            '成交金額': safe_float(r[2]),
                            '最高': safe_float(r[4]),
                            '最低': safe_float(r[5]),
                            '收盤': safe_float(r[6]),
                            '成交量(張)': int(safe_float(r[1]))
                        })
                else:
                    st.warning(f"⚠️ {date_str} 查無資料 (可能非交易月份或代號錯誤)")
            except Exception as e:
                st.error(f"❌ 請求失敗: {e}")

            progress_bar.progress((i + 1) / len(months))
            time.sleep(random.uniform(1.5, 2.5)) # 避免被封鎖

        status_text.empty()

        if data_list:
            df = pd.DataFrame(data_list)
            # 轉換並計算
            df[formula_label] = df.apply(lambda r: (r['成交金額'] / (r['最高'] - r['最低'])) / 100000000 if (r['最高'] - r['最低']) > 0 else 0, axis=1)
            avg_val = df[formula_label].mean()
            df['3倍異常'] = df[formula_label] > (avg_val * 3)
            
            st.success(f"✅ 成功抓取 {len(df)} 筆交易記錄！")
            
            # 表格顯示
            st.dataframe(
                df.style.apply(lambda r: ['color: #ef4444; font-weight: bold;' if r['3倍異常'] else '' for _ in r], axis=1),
                use_container_width=True
            )
        else:
            st.error("❌ 最終未抓得任何數據。建議確認代號是否為櫃買中心上市標的。")

else:
    # 上市部分保持原有的證交所邏輯
    st.title("🏛️ 上市個股分析 (證交所)")
    st.info("請輸入證交所掛牌之股票代號。")
