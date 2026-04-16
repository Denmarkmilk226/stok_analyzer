import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 페이지 설정 ---
st.set_page_config(page_title="Earnings-Driven Scenario Analyzer", layout="wide")

st.title("🎯 실적 지표 기반 3-Step 목표가 분석 툴")
st.markdown("""
실적 발표 데이터(EPS, 매출, 이익률 등)를 직접 조정하여 **명목성장률(g)**의 변화와 그에 따른 **목표 주가**를 시뮬레이션합니다.
""")

# --- 데이터 수집 함수 ---
@st.cache_data(ttl=3600)
def get_analysis_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y", interval="1wk")
        # 최근 분기 실적 데이터 가져오기
        q_financials = stock.quarterly_financials
        return {"info": info, "hist": hist, "q_fin": q_financials}
    except:
        return None

# --- 사이드바: 매크로 설정 ---
with st.sidebar:
    st.header("🌐 매크로 환경")
    ticker_input = st.text_input("미국 주식 티커", value="AVGO").upper()
    rf = st.slider("무위험 이자율 (10Y Treasury, %)", 2.0, 6.0, 4.2, 0.1) / 100
    erp = st.slider("위험 프리미엄 (ERP, %)", 3.0, 7.0, 5.0, 0.1) / 100
    k = rf + erp

# --- 메인 분석 영역 ---
if ticker_input:
    data = get_analysis_data(ticker_input)
    
    if data:
        info = data['info']
        hist = data['hist']
        q_fin = data['q_fin']
        
        # 1. 이전 분기 실적 및 가이던스 요약 (UI 배치용)
        st.subheader("📋 실적 지표 비교 및 시나리오 입력")
        
        # 기본값 세팅
        curr_price = info.get('currentPrice', 0)
        curr_eps = info.get('forwardEps', 1.0)
        curr_roe = info.get('returnOnEquity', 0.1)
        payout = info.get('payoutRatio', 0.0)
        
        # 사용자 조절 섹션 (Columns 활용)
        col_ref, col_input = st.columns([1, 2])
        
        with col_ref:
            st.info("💡 **참조 데이터 (최근 분기)**")
            try:
                # 최근 분기 매출 및 이익률 예시 (실제 데이터 매핑)
                last_rev = q_fin.loc['Total Revenue'].iloc[0] / 1e9 # 10억 달러 단위
                last_ni = q_fin.loc['Net Income'].iloc[0] / 1e9
                st.write(f"• 최근 매출: ${last_rev:.2f}B")
                st.write(f"• 순이익: ${last_ni:.2f}B")
                st.write(f"• 현재 ROE: {curr_roe*100:.1f}%")
                st.write(f"• 현재 EPS(Fwd): ${curr_eps:.2f}")
            except:
                st.write("분기 세부 지표 로드 중...")

        with col_input:
            st.success("📝 **사용자 시나리오 조정 (이번 발표 예상)**")
            input_mode = st.selectbox("조정할 핵심 지표 선택", ["EPS (Forward)", "ROE (성장성)", "매출 성장률 가중치"])
            
            if input_mode == "EPS (Forward)":
                user_val = st.number_input(f"예상 EPS 입력 (현재: ${curr_eps:.2f})", value=curr_eps * 1.1)
                final_eps = user_val
                final_roe = curr_roe
            elif input_mode == "ROE (성장성)":
                user_val = st.slider(f"예상 ROE 조정 (현재: {curr_roe*100:.1f}%)", 0.0, 1.0, curr_roe + 0.05)
                final_eps = curr_eps
                final_roe = user_val
            else:
                g_mult = st.slider("기존 g 대비 가중치 (1.0 = 유지)", 0.5, 2.0, 1.2)
                final_eps = curr_eps
                final_roe = curr_roe * g_mult

        # 2. 3-Step g 및 목표가 계산
        # Scenario A: Past
        g_past = (1 - payout) * curr_roe
        fv_past = (curr_eps * (1 - payout)) / (k - g_past) if k > g_past else curr_price
        
        # Scenario B: Guidance (가이드런스 상향 가정)
        g_guidance = g_past * 1.1
        fv_guidance = (curr_eps * 1.05 * (1 - payout)) / (k - g_guidance) if k > g_guidance else curr_price * 1.1
        
        # Scenario C: User (입력값 반영)
        g_user = (1 - payout) * final_roe
        if k > g_user:
            fv_user = (final_eps * (1 - payout)) / (k - g_user)
        else:
            fv_user = (final_eps * (1 - payout)) * (1 / k) * (1 + (g_user - k) * 15)

        # 3. 결과 시각화
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Past (기준)", f"${fv_past:.2f}", f"g={g_past*100:.1f}%")
        c2.metric("Guidance (시장)", f"${fv_guidance:.2f}", f"g={g_guidance*100:.1f}%")
        c3.metric("USER TARGET (예상)", f"${fv_user:.2f}", f"g={g_user*100:.1f}%", delta=f"{((fv_user/curr_price)-1)*100:.1f}%")

        # 메인 주가 차트
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='주간 종가', line=dict(color='white', width=2)))
        fig.add_hline(y=fv_past, line_dash="dot", line_color="gray", annotation_text="Past")
        fig.add_hline(y=fv_guidance, line_dash="dash", line_color="cyan", annotation_text="Guidance")
        fig.add_hline(y=fv_user, line_width=2, line_color="red", annotation_text="USER TARGET")
        
        fig.update_layout(height=500, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("데이터를 불러올 수 없습니다. 티커를 확인해 주세요.")
