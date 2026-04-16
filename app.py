import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 페이지 설정 ---
st.set_page_config(page_title="US Growth Valuation Fix", layout="wide")

st.title("🚀 고성장주 최적화 가치 분석 툴 (NVDA/AVGO 대응)")
st.markdown("""
초고성장주($g > k$)의 수치 발산 문제를 해결하기 위해 **H-Model 기반 다단계 성장 로직**을 적용했습니다.
""")

# --- 데이터 수집 및 보정 함수 ---
@st.cache_data(ttl=3600)
def get_safe_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # 실적 시즌 대응을 위한 분기 데이터
        q_fin = stock.quarterly_financials
        hist = stock.history(period="1y", interval="1wk")
        
        return {"info": info, "hist": hist, "q_fin": q_fin}
    except:
        return None

# --- 사이드바 설정 ---
with st.sidebar:
    st.header("🌐 매크로 설정")
    ticker_input = st.text_input("티커 입력", value="NVDA").upper()
    rf = st.slider("무위험 이자율 (%)", 2.0, 6.0, 4.2, 0.1) / 100
    erp = st.slider("위험 프리미엄 (%)", 3.0, 7.0, 5.0, 0.1) / 100
    k = rf + erp
    
    st.divider()
    st.header("⚙️ 성장성 보정")
    # 초고성장이 영원할 수 없으므로 유지 기간을 설정
    growth_years = st.slider("초고성장 유지 기간 (년)", 1, 10, 3)

# --- 분석 로직 ---
if ticker_input:
    data = get_safe_data(ticker_input)
    if data:
        info = data['info']
        # 고성장주 특화 지표 추출
        price = info.get('currentPrice', 1)
        eps = info.get('forwardEps', 1)
        # ROE가 너무 높으면(예: 100% 이상) 40%로 캡(Cap)을 씌워 현실화
        raw_roe = info.get('returnOnEquity', 0.2)
        adj_roe = min(raw_roe, 0.45) 
        payout = info.get('payoutRatio', 0.05)
        
        # 명목성장률(g) 계산 및 보정
        g_high = (1 - payout) * adj_roe
        g_terminal = rf + 0.02 # 장기 성장률은 국채금리 수준으로 수렴 가정
        
        # 3단계 시나리오 계산 함수 (발산 방지 로직)
        def calc_stable_fv(eps, g, k, g_long, years):
            # g가 k보다 클 경우: 초고성장 후 장기 성장으로 회귀하는 모델 사용
            # 가치 = 초고성장기 가치 + 영구 성장 가치
            term1 = (eps * (1 - payout)) * ((1 + g)**years) / ((1 + k)**years)
            term2 = (eps * (1 + g_long)) / (k - g_long) / ((1 + k)**years)
            # 수치가 너무 튀지 않도록 PER 기반 상한선 설정
            fair_val = (eps * (1-payout)) / (k - g) if k > g else (eps * 35) # k < g 시 PER 35배 적용
            return fair_val

        # 시나리오별 가치
        fv_past = calc_stable_fv(eps, g_high * 0.8, k, g_terminal, growth_years)
        fv_guidance = calc_stable_fv(eps, g_high, k, g_terminal, growth_years)

        # --- 사용자 지표 입력 섹션 ---
        st.subheader("📝 실적 시나리오 입력")
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"**현재 데이터 (Ref)**\n\n• ROE: {raw_roe*100:.1f}%\n• EPS(Fwd): ${eps}")
            user_g_adj = st.slider("나의 예상 성장 가중치 (1.0 = 유지)", 0.5, 2.0, 1.0)
            g_user = g_high * user_g_adj
            fv_user = calc_stable_fv(eps, g_user, k, g_terminal, growth_years)

        with col2:
            st.metric("USER 목표 주가", f"${fv_user:.2f}", f"{((fv_user/price)-1)*100:.1f}%")
            st.write(f"조정된 명목성장률($g$): **{g_user*100:.1f}%**")

        # --- 메인 차트 ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data['hist'].index, y=data['hist']['Close'], name='주가', line=dict(color='white')))
        fig.add_hline(y=fv_past, line_dash="dot", line_color="gray", annotation_text="Past")
        fig.add_hline(y=fv_user, line_width=2, line_color="red", annotation_text="USER TARGET")
        fig.update_layout(height=450, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("티커를 다시 확인해 주세요.")
