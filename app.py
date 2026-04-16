import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 페이지 설정 ---
st.set_page_config(page_title="US Growth Scenario Analyzer", layout="wide")

st.title("🚀 3-단계 성장 시나리오 기반 투자 분석 툴")
st.markdown("""
NH투자증권의 명목성장률($g$) 이론을 적용하여 세 가지 시나리오별 목표주가를 산출합니다.
""")

# --- 사이드바: 입력 및 설정 ---
with st.sidebar:
    st.header("🔍 분석 및 매크로 설정")
    ticker_input = st.text_input("미국 주식 티커", value="AVGO").upper()
    
    # 매크로 변수
    rf = st.slider("무위험 이자율 (US 10Y, %)", 2.0, 6.0, 4.2, 0.1) / 100
    erp = st.slider("위험 프리미엄 (ERP, %)", 3.0, 7.0, 5.0, 0.1) / 100
    k = rf + erp
    
    st.divider()
    st.header("🎯 사용자 시나리오 설정")
    # 현재 g 대비 몇 % 상향/하향할지 결정
    g_adjust_pct = st.slider("명목성장률(g) 조정 (%)", -50, 100, 20, 5) / 100
    
    st.info(f"현재 할인율(k): {k*100:.1f}%")

# --- 데이터 수집 함수 ---
@st.cache_data(ttl=3600)
def get_analysis_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y", interval="1wk")
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        return {"info": info, "hist": hist, "fin": financials, "bs": balance_sheet}
    except:
        return None

# --- 분석 실행 ---
if ticker_input:
    data = get_analysis_data(ticker_input)
    
    if data:
        info = data['info']
        hist = data['hist']
        
        # 기초 지표
        price = info.get('currentPrice', 0)
        eps = info.get('forwardEps', 1)
        roe = info.get('returnOnEquity', 0.1)
        payout = info.get('payoutRatio', 0)
        
        # 1. 시나리오별 g 산출
        g_past = (1 - payout) * roe  # 과거 확정치 기반
        g_guidance = g_past * 1.1    # 시장 기대치 (임의 가중치 1.1 반영)
        g_user = g_past * (1 + g_adjust_pct) # 사용자 조정치
        
        # 2. 시나리오별 목표주가 산출 (고든 모델)
        def calc_fair_value(eps, g, k, payout):
            if g >= k: return (eps * (1-payout)) * (1/k) * (1 + (g-k)*15)
            return (eps * (1-payout)) / (k - g)

        fv_past = calc_fair_value(eps, g_past, k, payout)
        fv_guidance = calc_fair_value(eps, g_guidance, k, payout)
        fv_user = calc_fair_value(eps, g_user, k, payout)

        # --- 상단 시나리오 비교 카드 ---
        st.subheader("🏁 시나리오별 목표가 비교")
        c1, c2, c3 = st.columns(3)
        
        c1.metric("Scenario A: Past", f"${fv_past:.2f}", f"g={g_past*100:.1f}%", delta_color="off")
        c2.metric("Scenario B: Guidance", f"${fv_guidance:.2f}", f"g={g_guidance*100:.1f}%", delta_color="normal")
        c3.metric("Scenario C: User (New)", f"${fv_user:.2f}", f"g={g_user*100:.1f}% (최종)", delta_color="inverse")

        st.divider()

        # --- 메인 차트: 3개 타겟 라인 시각화 ---
        st.subheader(f"📊 {ticker_input} 주가 흐름 및 시나리오별 타겟 라인")
        
        fig = go.Figure()
        # 주가 라인
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='현재 주가', line=dict(color='white', width=2)))
        
        # 과거 타겟 (회색 점선)
        fig.add_hline(y=fv_past, line_dash="dot", line_color="gray", annotation_text="Past Target")
        # 가이드런스 타겟 (파란 점선)
        fig.add_hline(y=fv_guidance, line_dash="dash", line_color="cyan", annotation_text="Guidance Target")
        # 사용자 타겟 (빨간 실선)
        fig.add_hline(y=fv_user, line_width=2, line_color="red", annotation_text="USER TARGET")
        
        fig.update_layout(height=500, margin=dict(l=10, r=10, t=30, b=10), template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        # --- 하단 듀퐁 분석 (질적 판단 보조) ---
        with st.expander("🧐 성장의 질 확인 (DuPont Analysis)"):
            try:
                ni = data['fin'].loc['Net Income'].iloc[0]
                rev = data['fin'].loc['Total Revenue'].iloc[0]
                ast = data['bs'].loc['Total Assets'].iloc[0]
                eq = data['bs'].loc['Stockholders Equity'].iloc[0]
                
                st.write(f"**순이익률**: {ni/rev*100:.1f}% | **자산회전율**: {rev/ast:.2f}x | **재무 레버리지**: {ast/eq:.2f}x")
                st.caption("실적 발표에서 위 지표들이 개선된다면 슬라이더를 더 과감하게 상향(%)하세요.")
            except:
                st.write("재무 데이터를 불러오는 중 오류가 발생했습니다.")

    else:
        st.error("데이터 로드 실패. 티커를 확인해 주세요.")
