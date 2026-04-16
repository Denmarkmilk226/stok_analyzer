import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 페이지 설정 ---
st.set_page_config(page_title="US Equity Growth Analyzer", layout="wide")

st.title("📈 명목성장률($g$) 기반 미국 주식 투자 분석 툴")
st.markdown("""
NH투자증권의 2026 경제 전망 이론을 바탕으로 설계되었습니다. 
**명목성장률($g$)**과 **요구수익률($k$)**의 관계를 통해 기업의 내재가치를 산출하고 주가 위치를 확인합니다.
""")

# --- 사이드바: 입력 및 설정 ---
with st.sidebar:
    st.header("🔍 분석 설정")
    ticker_input = st.text_input("미국 주식 티커 입력 (예: NVDA, AVGO, AAPL)", value="AVGO").upper()
    
    st.subheader("🌐 매크로 변수 설정")
    # 국채 금리 및 ERP 설정
    risk_free_rate = st.slider("무위험 이자율 (US 10Y Treasury, %)", 2.0, 6.0, 4.2, 0.1) / 100
    market_risk_premium = st.slider("주식 위험 프리미엄 (ERP, %)", 3.0, 7.0, 5.0, 0.1) / 100
    
    k = risk_free_rate + market_risk_premium
    st.info(f"현재 요구수익률(k): {k*100:.1f}%")

# --- 데이터 수집 함수 ---
@st.cache_data(ttl=3600)
def get_full_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 재무제표 데이터
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        # 주가 히스토리 (1년 주간 데이터)
        history = stock.history(period="1y", interval="1wk")
        
        return {
            "info": info,
            "financials": financials,
            "balance_sheet": balance_sheet,
            "history": history
        }
    except Exception as e:
        return None

# --- 분석 실행 ---
if ticker_input:
    data_bundle = get_full_data(ticker_input)
    
    if data_bundle:
        info = data_bundle['info']
        hist = data_bundle['history']
        
        # 주요 지표 추출
        current_price = info.get('currentPrice', 0)
        eps_forward = info.get('forwardEps', 1)
        roe = info.get('returnOnEquity', 0.1)
        payout = info.get('payoutRatio', 0)
        
        # 명목성장률 계산: g = (1 - 배당성향) * ROE
        g = (1 - payout) * roe
        
        # 적정 주가 계산 (고든 성장 모델 분해)
        if g >= k:
            # g가 k보다 클 경우 모델 한계를 고려한 프리미엄 방식 적용
            fair_value = eps_forward * (1 / k) * (1 + (g - k) * 10)
        else:
            fair_value = (eps_forward * (1 - payout)) / (k - g)

        # --- 상단 요약 지표 ---
        c1, c2, c3 = st.columns(3)
        c1.metric("현재 주가", f"${current_price:.2f}")
        upside = ((fair_value / current_price) - 1) * 100
        c2.metric("이론적 적정가", f"${fair_value:.2f}", f"{upside:.1f}%")
        c3.metric("명목성장률(g)", f"{g*100:.2f}%")

        st.divider()

        # --- 메인 차트: 주가 추이 및 목표가 타겟 ---
        st.subheader(f"📊 {ticker_input} 1개년 주가 추이 및 목표가 위치")
        
        fig_target = go.Figure()
        
        # 주간 종가 라인
        fig_target.add_trace(go.Scatter(
            x=hist.index, y=hist['Close'],
            mode='lines', name='주간 종가',
            line=dict(color='#00CC96', width=2.5)
        ))
        
        # 목표주가 수평선
        fig_target.add_hline(
            y=fair_value, 
            line_dash="dash", 
            line_color="red", 
            annotation_text=f"Target: ${fair_value:.2f}", 
            annotation_position="top left"
        )
        
        fig_target.update_layout(
            height=450,
            margin=dict(l=20, r=20, t=30, b=20),
            hovermode="x unified",
            xaxis_title="Date",
            yaxis_title="Price ($)"
        )
        st.plotly_chart(fig_target, use_container_width=True)

        # --- 중간 섹션: 듀퐁 분석 및 민감도 ---
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("📌 ROE 듀퐁 분석")
            try:
                ni = data_bundle['financials'].loc['Net Income'].iloc[0]
                rev = data_bundle['financials'].loc['Total Revenue'].iloc[0]
                ast = data_bundle['balance_sheet'].loc['Total Assets'].iloc[0]
                eq = data_bundle['balance_sheet'].loc['Stockholders Equity'].iloc[0]
                
                margin = ni / rev
                turnover = rev / ast
                lev = ast / eq
                
                st.write(f"• **순이익률**: {margin*100:.1f}%")
                st.write(f"• **자산회전율**: {turnover:.2f}x")
                st.write(f"• **재무 레버리지**: {lev:.2f}x")
                st.caption("회전율이 개선되는 기업은 실적 시즌 g의 상향 가능성이 높습니다.")
            except:
                st.warning("일부 재무 데이터를 불러올 수 없습니다.")

        with col_right:
            st.subheader("🔍 매크로 민감도 (Short)")
            # 콤팩트한 민감도 매트릭스
            g_range = np.linspace(g*0.8, g*1.2, 5)
            k_range = np.linspace(k*0.8, k*1.2, 5)
            
            z_data = []
            for g_v in g_range:
                row = []
                for k_v in k_range:
                    val = (eps_forward * (1-payout)) / (k_v - g_v) if k_v > g_v else eps_forward * (1/k_v)
                    row.append(val)
                z_data.append(row)
                
            fig_hm = px.imshow(
                z_data,
                x=[f"k={kv*100:.1f}%" for kv in k_range],
                y=[f"g={gv*100:.1f}%" for gv in g_range],
                labels=dict(x="요구수익률", y="성장률", color="적정가"),
                color_continuous_scale="RdYlGn",
                aspect="auto"
            )
            fig_hm.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_hm, use_container_width=True)

    else:
        st.error("티커 정보를 찾을 수 없습니다. 다시 확인해주세요.")
