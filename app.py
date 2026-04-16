import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# --- 페이지 설정 ---
st.set_page_config(page_title="US Growth Stock Analyzer", layout="wide")

st.title("📈 명목성장률($g$) 기반 미국 주식 투자 분석 툴")
st.markdown("""
NH투자증권의 2026 경제 전망 이론을 바탕으로 설계되었습니다. 
**명목성장률($g$)**과 **요구수익률($k$)**의 관계를 통해 기업의 내재가치를 산출합니다.
""")

# --- 사이드바: 입력 및 설정 ---
with st.sidebar:
    st.header("🔍 분석 설정")
    ticker_input = st.text_input("미국 주식 티커 입력 (예: NVDA, MSFT, AAPL)", value="NVDA").upper()
    
    st.subheader("🌐 매크로 변수 설정")
    # 미국 10년물 국채 금리 대용 (실시간 크롤링 가능하나 안정성을 위해 기본값 제공)
    risk_free_rate = st.slider("무위험 이자율 (k의 기초, %)", 2.0, 6.0, 4.2, 0.1) / 100
    market_risk_premium = st.slider("주식 위험 프리미엄 (ERP, %)", 3.0, 7.0, 5.0, 0.1) / 100
    
    st.info(f"현재 요구수익률(k): {(risk_free_rate + market_risk_premium)*100:.1f}%")

# --- 데이터 수집 함수 ---
@st.cache_data(ttl=3600)
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        # 기본 정보
        current_price = info.get('currentPrice')
        eps_forward = info.get('forwardEps')
        roe = info.get('returnOnEquity')
        payout_ratio = info.get('payoutRatio', 0)
        
        # 듀퐁 분석용 데이터
        net_income = financials.loc['Net Income'].iloc[0]
        revenue = financials.loc['Total Revenue'].iloc[0]
        total_assets = balance_sheet.loc['Total Assets'].iloc[0]
        equity = balance_sheet.loc['Stockholders Equity'].iloc[0]
        
        return {
            "name": info.get('shortName'),
            "price": current_price,
            "eps": eps_forward,
            "roe": roe,
            "payout": payout_ratio,
            "net_income": net_income,
            "revenue": revenue,
            "assets": total_assets,
            "equity": equity,
            "per_forward": info.get('forwardPE')
        }
    except Exception as e:
        return None

# --- 분석 엔진 ---
if ticker_input:
    data = get_stock_data(ticker_input)
    
    if data:
        k = risk_free_rate + market_risk_premium
        b = 1 - data['payout']  # 유보율
        g = b * data['roe']     # 명목성장률 (기본값)
        
        # 듀퐁 분석
        profit_margin = data['net_income'] / data['revenue']
        asset_turnover = data['revenue'] / data['assets']
        leverage = data['assets'] / data['equity']
        
        # 적정 주가 계산 (고든 모델)
        # P = D(1+g) / (k-g) -> 여기서는 단순화하여 Next Year Earnings 기반 적용
        # 만약 g >= k 이면 모델 한계 발생 (성장주 특성)
        if g >= k:
            fair_value = data['eps'] * (1/k) * (1 + (g-k)*10) # 성장 프리미엄 조정식
        else:
            fair_value = (data['eps'] * (1-data['payout'])) / (k - g)

        # --- UI 출력 ---
        col1, col2, col3 = st.columns(3)
        col1.metric("현재 주가", f"${data['price']:.2f}")
        col2.metric("이론적 적정가", f"${fair_value:.2f}", f"{((fair_value/data['price'])-1)*100:.1f}%")
        col3.metric("명목성장률(g)", f"{g*100:.2f}%")

        st.divider()

        # 1. 듀퐁 분석 섹션
        st.subheader("📌 ROE 듀퐁 분석 (성장의 질 검증)")
        dupont_col1, dupont_col2, dupont_col3 = st.columns(3)
        dupont_col1.write(f"**순이익률 (Margin)**: {profit_margin*100:.1f}%")
        dupont_col2.write(f"**자산회전율 (Efficiency)**: {asset_turnover:.2f}x")
        dupont_col3.write(f"**재무 레버리지 (Leverage)**: {leverage:.2f}x")
        
        st.info("2025-2026 국면에서는 금리 인하 시 '재무 레버리지'가 높으면서 '회전율'이 개선되는 기업이 유리합니다.")

        # 2. 시뮬레이션 히트맵
        st.subheader("📊 매크로 민감도 시뮬레이션 (k vs g)")
        
        g_range = np.linspace(max(0.01, g-0.03), g+0.03, 10)
        k_range = np.linspace(max(0.01, k-0.02), k+0.02, 10)
        
        z_data = []
        for g_val in g_range:
            row = []
            for k_val in k_range:
                if g_val >= k_val:
                    val = data['eps'] * (1/k_val) * (1 + (g_val-k_val)*10)
                else:
                    val = (data['eps'] * (1-data['payout'])) / (k_val - g_val)
                row.append(val)
            z_data.append(row)

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=[f"k={kv*100:.1f}%" for kv in k_range],
            y=[f"g={gv*100:.1f}%" for gv in g_range],
            colorscale='RdYlGn'
        ))
        fig.update_layout(title="성장률(g) 및 할인율(k) 변화에 따른 적정 주가 시뮬레이션")
        st.plotly_chart(fig, use_container_width=True)

        # 3. 데이터 다운로드
        st.subheader("📥 분석 결과 내보내기")
        report_df = pd.DataFrame({
            "Metric": ["Ticker", "Current Price", "Fair Value", "Nominal Growth (g)", "ROE"],
            "Value": [ticker_input, data['price'], fair_value, g, data['roe']]
        })
        csv = report_df.to_csv(index=False).encode('utf-8')
        st.download_button("CSV 리포트 다운로드", data=csv, file_name=f"{ticker_input}_analysis.csv", mime="text/csv")

    else:
        st.error("티커를 확인해주세요. 데이터를 가져올 수 없습니다.")

# 추가 디스커션 제안
st.divider()
st.caption("UCLA Postdoc Portfolio Analysis Tool v1.0")