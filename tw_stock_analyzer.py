import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 1. 環境初始化 ---
try:
    from FinMind.data import DataLoader
    FINMIND_AVAILABLE = True
    # 建立一個全局 DataLoader 實例
    dl = DataLoader()
except ImportError:
    FINMIND_AVAILABLE = False

# --- 2. 頁面設定 ---
st.set_page_config(page_title="台股分析工具 (FinMind 全方位版)", layout="wide")

if not FINMIND_AVAILABLE:
    st.error("⚠️ 偵測到環境未安裝 FinMind。請確認 requirements.txt 包含 FinMind 與 tqdm。")
    st.stop()

st.sidebar.header("功能選單")
mode = st.sidebar.selectbox(
    "請選擇分析模式", 
    ["上市個股分析 (FinMind)", "上櫃個股分析 (FinMind)"],
    key="finmind_nav_v1" 
)

formula_label = "成交金額/(最高-最低)/1億"

# --- 3. 核心數據處理邏輯 ---
def run_finmind_analysis(stock_id, start_date, end_date):
    """ 統一的 FinMind 抓取與分析邏輯 """
    try:
        with st.spinner(f'正在透過 FinMind 獲取 {stock_id} 數據...'):
            # 關鍵修正點：解決 NoneType 弱引用問題
            raw = dl.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
        
        if raw is not None and not raw.empty:
            df = pd.DataFrame()
            df['日期'] = raw['date']
            df['最高'] = raw['max']
            df['最低'] = raw['min']
            df['收盤'] = raw['close']
            # FinMind 的 Trading_money 單位是元，轉換成億元
            df['成交金額(億元)'] = (raw['Trading_money'] / 100000000).round(2)
            
            # 計算指標：成交金額(億) / (最高 - 最低)
            df[formula_label] = df.apply(
                lambda r: round(r['成交金額(億元)'] / (r['最高'] - r['最低']), 4) 
                if (r['最高'] - r['最低']) > 0 else 0, axis=1
            )
            
            # 根據選定範圍計算平均指標
            valid_scores = df[df[formula_label] > 0][formula_label]
            avg_score = valid_scores.mean() if not valid_scores.empty else 0
            threshold = avg_score * 3
            
            st.success(f"✅ {stock_id} 分析完成")
            st.info(f"📊 區間平均值：{avg_score:.4f} | 三倍異常門檻：{threshold:.4f}")
            
            # 套用紅字粗體標記
            def style_rows(row):
                is_extreme = row[formula_label] > threshold
                return ['color: red; font-weight: bold' if is_extreme else '' for _ in row]

            st.dataframe(df.style.apply(style_rows, axis=1), width='stretch')
        else:
            st.warning("⚠️ 查無數據。請確認代號正確，或該日期區間內有交易。")
            
    except Exception as e:
        # 攔截報錯避免 App 崩潰
        st.error(f"❌ 數據讀取異常：{str(e)}")
        st.info("💡 提示：若持續報錯，請嘗試縮小日期範圍。")

# --- 4. 模式執行 ---
if mode == "上市個股分析 (FinMind)":
    st.title("📈 上市個股分析 (FinMind 引擎)")
    col1, col2, col3 = st.columns(3)
    with col1: s_id = st.text_input("上市股票代號", value="2330")
    with col2: s_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: e_date = st.date_input("結束日期", value=datetime.today())
    
    if st.button("🚀 執行上市分析"):
        run_finmind_analysis(s_id, s_date, e_date)

elif mode == "上櫃個股分析 (FinMind)":
    st.title("📉 上櫃個股分析 (FinMind 引擎)")
    col1, col2, col3 = st.columns(3)
    with col1: s_id = st.text_input("上櫃股票代號", value="6104")
    with col2: s_date = st.date_input("開始日期", value=datetime.today() - timedelta(days=30))
    with col3: e_date = st.date_input("結束日期", value=datetime.today())
    
    if st.button("🔍 執行上櫃分析"):
        run_finmind_analysis(s_id, s_date, e_date)
