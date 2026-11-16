# ============================================================
# 🌱 우리 학교 극지식물 개체별 생육 차이 분석 대시보드
# 고등학교 수준에서 이해할 수 있도록 통계 용어 설명을 포함합니다.
# ============================================================

import io
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

import streamlit as st


# ────────────────────────────────────────────────────────────────
# 한글 폰트 CSS (Streamlit 깨짐 방지)
# ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────
# CSV 인코딩 자동 읽기 헬퍼
# utf-8-sig로 읽고 실패하면 cp949로 다시 읽는다.
# ────────────────────────────────────────────────────────────────
def read_csv_flexible(file) -> pd.DataFrame:
    try:
        df = pd.read_csv(file, encoding='utf-8-sig')
    except (UnicodeDecodeError, pd.errors.ParserError):
        file.seek(0)
        df = pd.read_csv(file, encoding='cp949')
    return df


# ────────────────────────────────────────────────────────────────
# 파일명에서 학교명 추출
# 예: '○○고_환경데이터.csv' → '○○고'
# ────────────────────────────────────────────────────────────────
def extract_school_name(filename: str) -> str:
    base = filename.split('.')[0]
    parts = base.split('_')
    return parts[0] if parts else filename


# ────────────────────────────────────────────────────────────────
# 환경 데이터 로딩 (@st.cache_data + spinner)
# ────────────────────────────────────────────────────────────────
@st.cache_data
def load_env_data(uploaded_file) -> pd.DataFrame:
    df = read_csv_flexible(uploaded_file)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], errors='coerce')
    return df


# ────────────────────────────────────────────────────────────────
# 생육 데이터 로딩 (@st.cache_data + spinner)
# ────────────────────────────────────────────────────────────────
@st.cache_data
def load_growth_data(uploaded_file) -> pd.DataFrame:
    return read_csv_flexible(uploaded_file)


# ────────────────────────────────────────────────────────────────
# 학교명 결정 (두 파일 중 먼저 올라온 것 기준)
# ────────────────────────────────────────────────────────────────
def get_school_display(env_file, growth_file) -> str:
    for f in (env_file, growth_file):
        if f is not None and f.name:
            name = extract_school_name(f.name)
            if name:
                return name
    return "우리 학교"


# ────────────────────────────────────────────────────────────────
# Plotly 한글 폰트 설정 (전 그래프 공통)
# ────────────────────────────────────────────────────────────────
PLOT_FONT = dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")


# ============================================================
#  Streamlit 앱 시작
# ============================================================
st.set_page_config(page_title="극지식물 생육 분석", layout="wide")


# ── 사이드바 ────────────────────────────────────────────────────
st.sidebar.title("📂 데이터 업로드")

env_file = st.sidebar.file_uploader(
    "환경 데이터 CSV",
    type="csv",
    help="컬럼 예시: time, temperature, humidity, ph, ec, water_temp, co2",
)
growth_file = st.sidebar.file_uploader(
    "생육 결과 데이터 CSV",
    type="csv",
    help=(
        "컬럼 예시: 개체번호, 잎 수(장), 지상부 길이(mm), 지하부길이(mm), "
        "생중량(g), 지상부질량(g), 지하부질량(g)"
    ),
)

if env_file is not None or growth_file is not None:
    school = get_school_display(env_file, growth_file)
    st.sidebar.success(f"✅ 업로드된 학교: **{school}**")
else:
    school = "우리 학교"

# 생육 측정 항목 선택 (생육 CSV 업로드 시에만 활성화)
growth_cols_full = [
    "잎 수(장)", "지상부 길이(mm)", "지하부길이(mm)",
    "생중량(g)", "지상부질량(g)", "지하부질량(g)",
]
selected_growth_metrics = st.sidebar.multiselect(
    "📏 생육 측정 항목 선택 (탭3 막대그래프에서 사용)",
    options=growth_cols_full,
    default=["생중량(g)", "잎 수(장)", "지상부 길이(mm)"],
    help="사이드바에서 선택한 항목만 막대그래프로 비교합니다.",
)

if env_file is None and growth_file is None:
    st.sidebar.info("📎 CSV 파일을 사이드바에 업로드해 주세요.")
    st.info("환경 데이터 CSV와 생육 결과 데이터 CSV를 업로드하면 분석이 시작됩니다.")
    st.stop()


# ── 데이터 로딩 (스피너 표시) ─────────────────────────────────
env_df = None
growth_df = None

if env_file is not None:
    with st.spinner("환경 데이터를 로딩 중입니다..."):
        env_df = load_env_data(env_file)

if growth_file is not None:
    with st.spinner("생육 결과 데이터를 로딩 중입니다..."):
        growth_df = load_growth_data(growth_file)


# ── 타이틀 ──────────────────────────────────────────────────────
st.title(f"🌱 {school} 극지식물 개체별 생육 차이 분석")
st.caption("고등학생도 이해할 수 있도록 주요 통계 용어에 짧은 설명을 붙였습니다.")


# ── 탭 정의 ─────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📖 실험 개요",
    "🌡️ 환경 데이터",
    "📊 생육 결과"
])


# ============================================================
#  Tab 1 — 실험 개요
# ============================================================
with tab1:
    st.header("연구 배경 및 목적")

    bg_text = f"""
**극지식물(Extremophile)** 은 고온·저온·고염 등 극한 환경에서도 살아남는 생물입니다.  
이 실험에서는 학교 실험실에서 배양한 극지식물 개체들의 **생육 차이**를 분석합니다.

- **생중량(g):** 물기를 뺀 실제 식물 무게. 생육 상태를 나타내는 가장 중요한 지표입니다.
- **평균(Mean):** 모든 개체의 값을 더해 개체 수로 나눈 값.
- **표준편차(Standard Deviation):** 값이 평균에서 얼마나 흩어져 있는지 나타내는 수치. 클수록 개체 간 차이가 큽니다.
- **CV(변동계수, Coefficient of Variation):** 표준편차를 평균으로 나눈 값(%로 표시). 서로 다른 단위나 규모의 데이터를 비교할 때 씁니다.
- **상관계수(Correlation Coefficient, r):** 두 변수가 함께 움직이는 정도. +1에 가까우면 같이 증가, -1에 가까우면 반대로 움직입니다. 0에 가까우면 뚜렷한 선형 관계가 없습니다.
"""
    st.markdown(bg_text)

    # ── 데이터 요약 표 ──────────────────────────────────────────
    st.subheader("데이터 요약")

    summary_rows = []
    if env_df is not None:
        time_col = 'time' if 'time' in env_df.columns else None
        if time_col is not None:
            valid_time = env_df[time_col].dropna()
            if not valid_time.empty:
                start = valid_time.min().strftime('%Y-%m-%d')
                end   = valid_time.max().strftime('%Y-%m-%d')
            else:
                start = end = "알 수 없음"
        else:
            start = end = "시간 정보 없음"

        env_cols_present = [c for c in ['temperature','humidity','ph','ec','water_temp','co2']
                            if c in env_df.columns]
        summary_rows.append({
            "구분": "환경 데이터",
            "규모": f"{len(env_df):,} 행",
            "측정 기간": f"{start} ~ {end}",
            "측정 항목": ", ".join(env_cols_present) if env_cols_present else "없음",
        })

    if growth_df is not None:
        growth_cols_present = [c for c in growth_cols_full if c in growth_df.columns]
        summary_rows.append({
            "구분": "생육 결과 데이터",
            "규모": f"{len(growth_df)} 개체",
            "측정 기간": "단일 시점 측정",
            "측정 항목": ", ".join(growth_cols_present) if growth_cols_present else "없음",
        })

    if summary_rows:
        st.table(pd.DataFrame(summary_rows).set_index("구분"))
    else:
        st.warning("업로드된 데이터가 없습니다.")

    # ── 주요 지표 카드 4개 ──────────────────────────────────────
    st.subheader("주요 지표 카드")

    col1, col2, col3, col4 = st.columns(4)

    # 카드 1 — 총 개체수
    if growth_df is not None:
        n_ind = len(growth_df)
        col1.metric("총 개체수", f"{n_ind} 개체",
                    help="분석 대상 극지식물 개체의 총 개수입니다.")
    else:
        col1.metric("총 개체수", "—", delta="데이터 없음")

    # 카드 2 — 평균 온도
    if env_df is not None and 'temperature' in env_df.columns:
        avg_temp = env_df['temperature'].mean()
        col2.metric("평균 온도", f"{avg_temp:.1f} °C",
                    help="측정 기간 동안 기록된 온도의 평균값입니다.")
    else:
        col2.metric("평균 온도", "—", delta="데이터 없음")

    # 카드 3 — 평균 습도
    if env_df is not None and 'humidity' in env_df.columns:
        avg_hum = env_df['humidity'].mean()
        col3.metric("평균 습도", f"{avg_hum:.1f} %",
                    help="측정 기간 동안 기록된 습도의 평균값입니다.")
    else:
        col3.metric("평균 습도", "—", delta="데이터 없음")

    # 카드 4 — 평균 생중량
    if growth_df is not None and '생중량(g)' in growth_df.columns:
        avg_bw = growth_df['생중량(g)'].mean()
        col4.metric("평균 생중량", f"{avg_bw:.2f} g",
                    help="모든 개체의 생중량(물기 뺀 무게) 평균입니다.")
    else:
        col4.metric("평균 생중량", "—", delta="데이터 없음")


# ============================================================
#  Tab 2 — 환경 데이터
# ============================================================
with tab2:
    if env_df is None:
        st.error("환경 데이터를 업로드해 주세요. (사이드바 → 환경 데이터 CSV)")
        st.stop()

    # ── 환경 요약 표 (평균·최소·최대) ───────────────────────────
    st.subheader("📋 환경 데이터 요약 (평균 · 최소 · 최대)")

    env_summary_keys = ['temperature', 'humidity', 'ph', 'ec', 'water_temp', 'co2']
    env_present = [k for k in env_summary_keys if k in env_df.columns]

    if env_present:
        rows = []
        for col in env_present:
            s = env_df[col].dropna()
            rows.append({
                "측정 항목": col,
                "평균": f"{s.mean():.2f}",
                "최소": f"{s.min():.2f}",
                "최대": f"{s.max():.2f}",
            })
        st.table(pd.DataFrame(rows).set_index("측정 항목"))
    else:
        st.warning("환경 데이터에 인식할 수 있는 측정 항목(temperature, humidity, ph, ec 등)이 없습니다.")

    # ── 날짜별 시계열 (일별 평균 꺾은선) ─────────────────────────
    st.subheader("📅 날짜별 시계열 (일별 평균)")

    if 'time' in env_df.columns:
        env_t = env_df.copy()
        env_t['date'] = env_t['time'].dt.date

        daily_cols = [c for c in ['temperature', 'humidity', 'ph', 'ec'] if c in env_t.columns]

        if daily_cols:
            daily = env_t.groupby('date')[daily_cols].mean().reset_index()
            daily['date'] = pd.to_datetime(daily['date'])

            n_trace = len(daily_cols)
            fig_env = make_subplots(
                rows=n_trace,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.10,
                subplot_titles=[f"{c} 변화" for c in daily_cols],
            )

            colors_map = {
                'temperature': '#FF6B6B',
                'humidity':    '#4ECDC4',
                'ph':          '#A78BFA',
                'ec':          '#FCD34D',
            }

            for i, col in enumerate(daily_cols, start=1):
                fig_env.add_trace(
                    go.Scatter(
                        x=daily['date'],
                        y=daily[col],
                        mode='lines+markers',
                        name=col,
                        line=dict(color=colors_map.get(col, '#636EFA'), width=2),
                        marker=dict(size=4),
                    ),
                    row=i, col=1,
                )

            fig_env.update_layout(
                height=100 + 130 * n_trace,
                font=PLOT_FONT,
                showlegend=False,
                margin=dict(l=44, r=16, t=40, b=32),
            )
            fig_env.update_xaxes(tickformat='%m/%d', row=n_trace, col=1)
            st.plotly_chart(fig_env)
        else:
            st.info("꺾은선으로 그릴 수 있는 환경 측정 항목(temperature, humidity, ph, ec)이 없습니다.")
    else:
        st.warning("환경 데이터에서 'time' 컬럼을 찾을 수 없습니다.")

    # ── expander: 원본 테이블 + CSV 다운로드 ────────────────────
    with st.expander("📁 환경 데이터 원본 테이블 + CSV 다운로드"):
        st.dataframe(env_df, width='stretch')

        csv_bytes = env_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇ 환경 데이터 CSV 다운로드",
            data=csv_bytes,
            file_name=f"{school}_환경데이터.csv",
            mime="text/csv",
        )


# ============================================================
#  Tab 3 — 생육 결과
# ============================================================
with tab3:
    if growth_df is None:
        st.error("생육 결과 데이터를 업로드해 주세요. (사이드바 → 생육 결과 CSV)")
        st.stop()

    has_biomass  = '생중량(g)'       in growth_df.columns
    has_leaf     = '잎 수(장)'      in growth_df.columns
    has_shoot    = '지상부 길이(mm)' in growth_df.columns
    has_root     = '지하부길이(mm)'  in growth_df.columns
    has_shoot_m  = '지상부질량(g)'   in growth_df.columns
    has_root_m   = '지하부질량(g)'   in growth_df.columns

    if not has_biomass:
        st.error("생육 데이터에 '생중량(g)' 컬럼이 없습니다. 그래프를 표시할 수 없습니다.")
        st.stop()

    # ── 🥇 핵심 결과 카드 ────────────────────────────────────────
    st.header("🥇 핵심 결과")

    avg_bw   = growth_df['생중량(g)'].mean()
    max_idx  = growth_df['생중량(g)'].idxmax()
    min_idx  = growth_df['생중량(g)'].idxmin()
    max_row  = growth_df.loc[max_idx]
    min_row  = growth_df.loc[min_idx]

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "📊 평균 생중량",
        f"{avg_bw:.2f} g",
        help="모든 개체의 생중량(g) 평균. 생육 상태의 중심 지표입니다.",
    )
    c2.metric(
        "🏆 최대 개체 생중량",
        f"{max_row['생중량(g)']:.2f} g",
        delta=f"개체번호 {int(max_row['개체번호'])}",
        help="생중량이 가장 큰 개체입니다.",
    )
    c3.metric(
        "🔻 최소 개체 생중량",
        f"{min_row['생중량(g)']:.2f} g",
        delta=f"개체번호 {int(min_row['개체번호'])}",
        help="생중량이 가장 작은 개체입니다.",
    )

    # ── 개체별 생육 비교 (막대 그래프) ───────────────────────────
    st.subheader("📊 개체별 생육 비교 (막대 그래프)")

    metric_map = {
        "잎 수(장)":       has_leaf,
        "지상부 길이(mm)": has_shoot,
        "지하부길이(mm)":  has_root,
        "생중량(g)":       has_biomass,
        "지상부질량(g)":   has_shoot_m,
        "지하부질량(g)":   has_root_m,
    }
    available_metrics = [m for m, ok in metric_map.items() if ok]
    chosen = [m for m in selected_growth_metrics if m in available_metrics]
    if not chosen:
        chosen = available_metrics

    bw_col = '생중량(g)' if has_biomass else None
    top25_threshold = growth_df[bw_col].quantile(0.75) if bw_col else None
    bot25_threshold = growth_df[bw_col].quantile(0.25) if bw_col else None

    # 상위·하위 25% 개체번호 집합
    top25_ids = set(growth_df.loc[growth_df[bw_col] >= top25_threshold, '개체번호'].tolist()) if bw_col else set()
    bot25_ids = set(growth_df.loc[growth_df[bw_col] <= bot25_threshold, '개체번호'].tolist()) if bw_col else set()

    bar_cols = st.columns(min(len(chosen), 3))
    for idx, metric in enumerate(chosen[:3]):
        with bar_cols[idx]:
            df_plot = growth_df[['개체번호', metric]].copy()
            df_plot = df_plot.sort_values(metric, ascending=False).reset_index(drop=True)

            colors_bar = [
                '#2ECC71' if row['개체번호'] in top25_ids else   # 초록: 상위 25%
                '#E74C3C' if row['개체번호'] in bot25_ids else   # 빨강: 하위 25%
                '#85C1E9'                                          # 파랑: 중간
                for _, row in df_plot.iterrows()
            ]

            fig_bar = px.bar(
                df_plot,
                x='개체번호',
                y=metric,
                color=colors_bar,
            )
            fig_bar.update_traces(marker=dict(line=dict(width=0.5, color='white')))
            fig_bar.update_layout(
                font=PLOT_FONT,
                height=280,
                margin=dict(l=44, r=16, t=30, b=36),
                xaxis_title="개체번호",
                yaxis_title=metric,
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_bar)

    if len(chosen) > 3:
        st.info(f"선택한 지표 {len(chosen)}개 중 첫 3개를 표시합니다. 사이드바에서 항목을 조정할 수 있습니다.")

    # ── 생중량 분포 (박스플롯) ────────────────────────────────────
    st.subheader("📦 생중량 분포 (박스플롯)")
    st.caption(
        "**박스플롯(Box Plot):** 데이터의 분포와 이상치를 한눈에 보는 그래프. "
        "상자 위아래 선은 상위 25%·하위 25% 경계, 상자 안은 중간 50%, 굵은 선은 중앙값입니다. "
        "상자 밖 점은 이상치(outlier)로 간주됩니다."
    )

    fig_box = px.box(
        growth_df,
        y='생중량(g)',
        points="outliers",
    )
    fig_box.update_traces(marker=dict(color='#F39C12', size=5))
    fig_box.update_layout(
        font=PLOT_FONT,
        height=320,
        margin=dict(l=44, r=16, t=30, b=36),
        yaxis_title="생중량 (g)",
    )
    fig_box.add_hline(
        y=avg_bw,
        line_dash="dash",
        line_color="#E74C3C",
        annotation_text=f"평균 = {avg_bw:.2f} g",
        annotation_position="right",
        annotation_font=dict(size=11, color="#E74C3C"),
    )
    st.plotly_chart(fig_box)

    # ── 표준편차·CV 요약 카드 ─────────────────────────────────────
    std_bw = growth_df['생중량(g)'].std()
    cv_bw  = (std_bw / avg_bw * 100) if avg_bw > 0 else 0.0
    st.info(
        f"**생중량 분포 요약**  "
        f"평균 = {avg_bw:.2f} g  |  "
        f"표준편차 = {std_bw:.2f} g  |  "
        f"CV(변동계수) = {cv_bw:.1f}%  —  "
        f"CV가 작을수록 개체 간 생중량 차이가 적습니다.",
        icon="📐",
    )

    # ── 상관관계 분석 (산점도 2개) ────────────────────────────────
    st.subheader("🔗 상관관계 분석 (산점도)")

    corr_done = False

    if has_leaf and has_biomass:
        corr_done = True
        leaf_vals = growth_df['잎 수(장)'].values
        bw_vals   = growth_df['생중량(g)'].values
        r_leaf, _ = stats.pearsonr(leaf_vals, bw_vals)

        fig_ls = make_subplots(rows=1, cols=1)
        fig_ls.add_trace(
            go.Scatter(
                x=growth_df['잎 수(장)'],
                y=growth_df['생중량(g)'],
                mode='markers',
                marker=dict(
                    size=10,
                    color=growth_df['생중량(g)'],
                    colorscale='Viridis',
                    line=dict(width=0.5, color='white'),
                ),
                name='개체',
            )
        )
        fig_ls.add_hline(y=avg_bw, line_dash="dot", line_color="#E74C3C")
        fig_ls.add_vline(x=growth_df['잎 수(장)'].mean(),
                         line_dash="dot", line_color="#3498DB")

        fig_ls.update_layout(
            font=PLOT_FONT,
            height=360,
            margin=dict(l=52, r=16, t=40, b=52),
            xaxis_title="잎 수 (장)",
            yaxis_title="생중량 (g)",
            title=dict(
                text=f"잎 수 vs 생중량  (상관계수 r = {r_leaf:.3f})",
                font=dict(size=14),
            ),
        )
        st.plotly_chart(fig_ls)

        direction = "증가하는 경향" if r_leaf > 0 else "감소하는 경향"
        st.caption(
            f"상관계수 r = {r_leaf:.3f}  —  잎 수가 많을수록 생중량도 {direction}이 있습니다. "
            "r이 0에 가까우면 뚜렷한 선형 관계가 없다는 뜻입니다."
        )

    if has_shoot and has_biomass:
        corr_done = True
        shoot_vals = growth_df['지상부 길이(mm)'].values
        bw_vals    = growth_df['생중량(g)'].values
        r_shoot, _ = stats.pearsonr(shoot_vals, bw_vals)

        fig_ss = make_subplots(rows=1, cols=1)
        fig_ss.add_trace(
            go.Scatter(
                x=growth_df['지상부 길이(mm)'],
                y=growth_df['생중량(g)'],
                mode='markers',
                marker=dict(
                    size=10,
                    color=growth_df['생중량(g)'],
                    colorscale='Plasma',
                    line=dict(width=0.5, color='white'),
                ),
                name='개체',
            )
        )
        fig_ss.add_hline(y=avg_bw, line_dash="dot", line_color="#E74C3C")
        fig_ss.add_vline(x=growth_df['지상부 길이(mm)'].mean(),
                         line_dash="dot", line_color="#3498DB")

        fig_ss.update_layout(
            font=PLOT_FONT,
            height=360,
            margin=dict(l=52, r=16, t=40, b=52),
            xaxis_title="지상부 길이 (mm)",
            yaxis_title="생중량 (g)",
            title=dict(
                text=f"지상부 길이 vs 생중량  (상관계수 r = {r_shoot:.3f})",
                font=dict(size=14),
            ),
        )
        st.plotly_chart(fig_ss)

        direction = "증가하는 경향" if r_shoot > 0 else "감소하는 경향"
        st.caption(
            f"상관계수 r = {r_shoot:.3f}  —  지상부 길이가 길수록 생중량도 {direction}이 있습니다."
        )

    if not corr_done:
        st.info("산점도를 그릴 수 있는 지표(잎 수, 지상부 길이)가 데이터에 없습니다.")

    # ── 생중량 상위 25% vs 하위 25% 비교 ─────────────────────────
    st.subheader("🎯 생중량 상위 25% vs 하위 25% 개체 비교")

    if bw_col is not None and len(top25_ids) > 0 and len(bot25_ids) > 0:
        top25 = growth_df.loc[growth_df['개체번호'].isin(top25_ids)].sort_values(bw_col, ascending=False)
        bot25 = growth_df.loc[growth_df['개체번호'].isin(bot25_ids)].sort_values(bw_col, ascending=True)

        all_cols = ['개체번호','잎 수(장)','지상부 길이(mm)','지하부길이(mm)',
                    '생중량(g)','지상부질량(g)','지하부질량(g)']
        disp_cols = [c for c in all_cols if c in top25.columns]

        st.markdown("### 🟢 상위 25% (생중량이 가장 큰 개체들)")
        st.dataframe(top25[disp_cols].reset_index(drop=True), width='stretch')

        st.markdown("### 🔻 하위 25% (생중량이 가장 작은 개체들)")
        st.dataframe(bot25[disp_cols].reset_index(drop=True), width='stretch')

        # 평균 비교 표
        comp_rows = []
        for col in disp_cols:
            if col != '개체번호':
                t_avg = top25[col].mean()
                b_avg = bot25[col].mean()
                comp_rows.append({
                    "측정 항목": col,
                    "상위 25% 평균": f"{t_avg:.2f}",
                    "하위 25% 평균": f"{b_avg:.2f}",
                    "차이 (상위−하위)": f"{t_avg - b_avg:.2f}",
                })
        if comp_rows:
            st.table(pd.DataFrame(comp_rows).set_index("측정 항목"))

    # ── expander: 생육 데이터 원본 + CSV 다운로드 ────────────────
    with st.expander("📁 생육 데이터 원본 테이블 + CSV 다운로드"):
        st.dataframe(growth_df, width='stretch')

        csv_bytes = growth_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇ 생육 결과 데이터 CSV 다운로드",
            data=csv_bytes,
            file_name=f"{school}_생육결과데이터.csv",
            mime="text/csv",
        )
