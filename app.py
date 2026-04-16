import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 페이지 설정 ---
st.set_page_config(page_title="Earnings-Led Scenario Analyzer", layout="wide")

st.title("🎯 실적 지표 기반 맞춤형 목표가 분석 툴")
st.markdown("""
최근 실적과 가이던스를 참고하여 **사용자가 직접 예상 실적 지표를 입력**하고, 그에 따른 적정 주가 변화를 분석합니다.
""")

# --- 데이터 수집 함수 (Broadcom 실적 데이터 반영) ---
@st.cache_data(ttl=3600)
def get_analysis_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 2026 Q1 실제 데이터 (검색 결과 반영)
        actual_q1 = {
            "revenue": 19311,  # $19.3B
            "net_income": 10185, # Non-GAAP $10.2B
            "eps": 2.05,
            "ebitda_margin": 68.0
        }
        # 2026 Q2 가이던스 데이터
        guidance_q2 = {
            "revenue": 22000, # $22.0B
            "ebitda_margin": 68.0
        }
        return {
            "info": stock.info,
            "hist": stock.history(period="1y", interval="1wk"),
            "actual": actual_q1,
            "guidance": guidance_q2
        }
    except:
        return None

# --- 사이드바: 매크로 환경 설정 ---
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
        # 1. 실적 지표 비교 및 시나리오 입력 섹션
        st.subheader("📋 실적 지표 비교 및 사용자 입력")
        
        col_actual, col_guide, col_user = st.columns(3)
        
        # 실제 실적 (Actual Q1)
        with col_actual:
            st.info("📊 **이전 분기 실적 (Q1 '26)**")
            st.write(f"• 매출: **${data['actual']['revenue']/1000:.2f}B**")
            st.write(f"• 순이익: **${data['actual']['net_income']/1000:.2f}B**")
            st.write(f"• EPS: **${data['actual']['eps']:.2f}**")
            st.write(f"• EBITDA 이익률: **{data['actual']['ebitda_margin']}%**")

        # 기업 가이던스 (Guidance Q2)
        with col_guide:
            st.warning("🚀 **차기 가이던스 (Q2 '26)**")
            st.write(f"• 매출 가이드: **~${data['guidance']['revenue']/1000:.2f}B**")
            st.write(f"• EBITDA 가이드: **~{data['guidance']['ebitda_margin']}%**")
            st.write(f"• AI 매출 전망: **$10.7B**") # 검색 결과 반영
            st.caption("기업이 공식 발표한 수치입니다.")

        # 사용자 시나리오 입력
        with col_user:
            st.success("📝 **나의 예상치 입력**")
            metric_choice = st.selectbox("조정할 지표", ["EPS (Forward)", "매출 성장률", "자기자본이익률(ROE)"])
            
            payout = data['info'].get('payoutRatio', 0.4)
            curr_roe = data['info'].get('returnOnEquity', 0.15)
            curr_eps = data['info'].get('forwardEps', 2.05)
            
            if metric_choice == "EPS (Forward)":
                final_eps = st.number_input("예상 EPS ($)", value=curr_eps * 1.1)
                final_roe = curr_roe
            elif metric_choice == "매출 성장률":
                growth_adj = st.slider("성장 가중치 (1.0 = 유지)", 0.5, 2.0, 1.2)
                final_eps = curr_eps
                final_roe = curr_roe * growth_adj
            else:
                final_roe = st.slider("예상 ROE (%)", 0.0, 1.0, curr_roe + 0.05)
                final_eps = curr_eps

        # 2. 목표가 계산 (고든 성장 모델)
        g_past = (1 - payout) * curr_roe
        g_user = (1 - payout) * final_roe
        
        def get_fv(e, g, k_val, p):
            if g >= k_val: return (e * (1-p)) * (1/k_val) * (1 + (g-k_val)*12)
            return (e * (1-p)) / (k_val - g)

        fv_past = get_fv(curr_eps, g_past, k, payout)
        fv_user = get_fv(final_eps, g_user, k, payout)

        # 3. 결과 대시보드 및 차트
        st.divider()
        res_c1, res_c2 = st.columns([1, 2])
        
        with res_c1:
            st.metric("과거 실적 기반 적정가", f"${fv_past:.2f}")
            st.metric("USER 목표 주가", f"${fv_user:.2f}", f"{((fv_user/data['info']['currentPrice'])-1)*100:.1f}%")
            st.write(f"현재 명목성장률($g$): **{g_user*100:.2f}%**")

        with res_c2:
            fig = go.Figure()
            # 주가 차트
            fig.add_trace(go.Scatter(x=data['hist'].index, y=data['hist']['Close'], name='주간 종가', line=dict(color='white')))
            # 타겟 라인
            fig.add_hline(y=fv_past, line_dash="dot", line_color="gray", annotation_text="Past Target")
            fig.add_hline(y=fv_user, line_width=2, line_color="red", annotation_text="USER TARGET")
            
            fig.update_layout(height=400, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("데이터 로드 실패. 티커를 다시 확인해 주세요.")
