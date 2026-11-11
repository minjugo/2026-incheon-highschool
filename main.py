import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
from datetime import date

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="송도고 극지식물 생육 대시보드",
    layout="wide",
    page_icon="🌱",
)

# ─────────────────────────────────────────────
# 한글 폰트 CSS (Streamlit + Plotly 공용)
# ─────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"], .stMarkdown, .stTable, .stMetric {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif !important;
}
</style>
""",
    unsafe_allow_html=True,
)

PLOT_FONT = dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif")


# ─────────────────────────────────────────────
# 데이터 로딩 (캐싱)
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_data():
    """data/ 폴더에서 CSV를 NFC/NFD 정규화 후 인식."""
    DATA_DIR = Path(__file__).parent / "data"
    env_df = None
    growth_df = None
    if not DATA_DIR.exists():
        return env_df, growth_df
    for f in DATA_DIR.iterdir():
        name = unicodedata.normalize("NFC", f.name)
        if not name.endswith(".csv"):
            continue
        if "환경" in name:
            env_df = pd.read_csv(f, encoding="utf-8-sig")
        elif "생육" in name:
            growth_df = pd.read_csv(f, encoding="utf-8-sig")
    return env_df, growth_df


def find_column(df, keywords):
    """데이터프레임에서 키워드 중 하나라도 포함된 컬럼명을 반환."""
    if df is None or df.columns is None:
        return None
    for col in df.columns:
        col_norm = unicodedata.normalize("NFC", str(col)).strip()
        for kw in keywords:
            if kw.lower() in col_norm.lower():
                return col
    return None


def get_datetime_series(df, time_col):
    """time 컬럼을 datetime으로 파싱."""
    if time_col is None or df is None:
        return None
    series = pd.to_datetime(df[time_col], errors="coerce")
    return series


# ─────────────────────────────────────────────
# 통계 헬퍼
# ─────────────────────────────────────────────
def describe_stats(series):
    """평균·중앙값·표준편차·CV·최소·최대 반환."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return {"평균": np.nan, "중앙값": np.nan, "표준편차": np.nan,
                "CV(%)": np.nan, "최소": np.nan, "최대": np.nan, "N": 0}
    mean = s.mean()
    std = s.std(ddof=0)
    cv = (std / mean * 100) if mean != 0 else np.nan
    return {
        "평균": mean,
        "중앙값": s.median(),
        "표준편차": std,
        "CV(%)": cv,
        "최소": s.min(),
        "최대": s.max(),
        "N": len(s),
    }


# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
st.sidebar.title("⚙️ 설정")

with st.spinner("데이터를 불러오는 중..."):
    env_df, growth_df = load_data()

# 데이터 존재 확인
if env_df is None and growth_df is None:
    st.error("data/ 폴더에서 환경 데이터('환경')와 생육 데이터('생육')를 찾을 수 없습니다.")
    st.stop()
elif env_df is None:
    st.warning("환경 데이터('환경'이 포함된 CSV)를 찾을 수 없습니다. 환경 탭은 비워집니다.")
elif growth_df is None:
    st.warning("생육 데이터('생육'이 포함된 CSV)를 찾을 수 없습니다. 생육 탭은 비워집니다.")

# 환경 데이터 숫자형 변환 (값 뒤 공백 등 대비)
if env_df is not None:
    for c in env_df.columns:
        if c != env_df.columns[0]:
            env_df[c] = pd.to_numeric(env_df[c], errors="coerce")

# ── 생육 항목 선택 ──
growth_col_map = {
    "잎 수": ["잎 수", "잎수", "leaf"],
    "지상부 길이": ["지상부 길이", "지상부길이", "지상부"],
    "지하부 길이": ["지하부 길이", "지하부길이", "지하부"],
    "생중량": ["생중량", "생 중량", "fresh"],
}
selected_metric = st.sidebar.selectbox(
    "📊 생육 항목 선택",
    options=list(growth_col_map.keys()),
    index=3,  # 기본: 생중량
)

# ── 환경 데이터 날짜 범위 ──
time_col = find_column(env_df, ["time", "시간", "date", "일자", "date_time"])
env_dates = None
start_date = None
end_date = None

if time_col is not None:
    dt_series = get_datetime_series(env_df, time_col)
    if dt_series is not None and dt_series.notna().any():
        env_dates = dt_series
        min_d = dt_series.min().date()
        max_d = dt_series.max().date()
        start_date = st.sidebar.date_input(
            "📅 환경 데이터 시작 날짜",
            value=min_d,
            min_value=min_d,
            max_value=max_d,
        )
        end_date = st.sidebar.date_input(
            "📅 환경 데이터 종료 날짜",
            value=max_d,
            min_value=min_d,
            max_value=max_d,
        )
        if start_date > end_date:
            st.sidebar.error("시작 날짜가 종료 날짜보다 늦습니다.")
    else:
        st.sidebar.info("환경 데이터의 시간 컬럼을 파싱할 수 없습니다.")
else:
    st.sidebar.info("환경 데이터에서 시간(time) 컬럼을 찾을 수 없습니다.")

# ─────────────────────────────────────────────
# 제목
# ─────────────────────────────────────────────
st.title("🌱 송도고 극지식물 개체별 생육 차이 분석")
st.caption("과학 탐구 실험 결과를 웹 대시보드로 시각화 — 에코스마트팜 극지식물 재배 프로젝트")

# ─────────────────────────────────────────────
# 데이터 전처리 (컬럼 매핑)
# ─────────────────────────────────────────────
leaf_col = find_column(growth_df, growth_col_map["잎 수"])
shoot_col = find_column(growth_df, growth_col_map["지상부 길이"])
root_col = find_column(growth_df, growth_col_map["지하부 길이"])
weight_col = find_column(growth_df, growth_col_map["생중량"])
id_col = find_column(growth_df, ["개체번호", "개체 번호", "id", "번호"])

temp_col = find_column(env_df, ["temperature", "온도", "temp"])
hum_col = find_column(env_df, ["humidity", "습도", "hum"])
ph_col = find_column(env_df, ["ph", "수소이온농도"])
ec_col = find_column(env_df, ["ec", "전기전도도"])

# ─────────────────────────────────────────────
# 탭 구성
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 변화", "📊 생육 결과"])

# ═════════════════════════════════════════════
# TAB 1 — 실험 개요
# ═════════════════════════════════════════════
with tab1:
    st.header("📖 실험 개요")

    st.markdown("""
**연구 배경**

극지방 식물(극지식물)은 낮은 온도와 제한된 환경에서도 생존하는 강인한 생리적 특성을 지닙니다.
본 실험은 스마트팜 환경에서 극지식물을 재배하며, **같은 조건에서도 개체마다 생육 차이가 나타나는지**를
개체별 측정 데이터를 통해 확인하는 탐구 활동입니다.

**우리 팀의 가설**

1. 같은 스마트팜에서 재배해도 **개체별 생중량 차이(분산)는 클 것이다.**
   → 개체마다 생장 속도, 뿌리 발달, 잎 발달이 다르기 때문에 평균 주변에 모여 있기보다
   편차가 크게 나타날 것으로 예상.
2. **잎 수가 많은 개체의 생중량이 더 클 것이다.**
   → 잎은 광합성 기관이며 생체량과 직결되므로, 잎 수가 많을수록 전체 무게(생중량)가 증가할 것으로 예상.
""")

    st.divider()

    # 데이터 요약 표
    env_rows = 0
    env_period = "—"
    env_interval = "1시간 간격 (센서 자동 측정)"
    growth_individuals = 0

    if env_df is not None and not env_df.empty:
        env_rows = len(env_df)
        if time_col is not None:
            dt_s = get_datetime_series(env_df, time_col)
            if dt_s is not None and dt_s.notna().any():
                env_period = f"{dt_s.min().strftime('%Y-%m-%d')} ~ {dt_s.max().strftime('%Y-%m-%d')}"

    if growth_df is not None and not growth_df.empty:
        growth_individuals = len(growth_df)

    summary_data = {
        "데이터": ["환경 데이터", "생육 결과 데이터"],
        "설명": [
            f"측정 기간: {env_period} / 측정 간격: {env_interval} / 총 행 수: {env_rows}행",
            f"개체 수: {growth_individuals}개체 / 측정 시점: 수확 시 1회 / 측정일·위치 정보: 없음",
        ],
    }
    st.table(pd.DataFrame(summary_data))

    st.divider()

    # 핵심 지표 카드 4개
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="🧪 개체 수", value=f"{growth_individuals}개체" if growth_individuals else "0")

    with col2:
        if weight_col is not None and growth_df is not None and not growth_df.empty:
            avg_w = pd.to_numeric(growth_df[weight_col], errors="coerce").mean()
            st.metric(label="⚖️ 평균 생중량", value=f"{avg_w:.2f} g")
        else:
            st.metric(label="⚖️ 평균 생중량", value="데이터 없음")

    with col3:
        if temp_col is not None and env_df is not None and not env_df.empty:
            avg_t = env_df[temp_col].mean()
            st.metric(label="🌡️ 평균 온도", value=f"{avg_t:.1f} ℃")
        else:
            st.metric(label="🌡️ 평균 온도", value="데이터 없음")

    with col4:
        if hum_col is not None and env_df is not None and not env_df.empty:
            avg_h = env_df[hum_col].mean()
            st.metric(label="💧 평균 습도", value=f"{avg_h:.1f} %")
        else:
            st.metric(label="💧 평균 습도", value="데이터 없음")

# ═════════════════════════════════════════════
# TAB 2 — 환경 변화
# ═════════════════════════════════════════════
with tab2:
    st.header("🌡️ 환경 변화")

    if env_df is None or env_df.empty:
        st.error("환경 데이터가 없습니다. data/ 폴더에 '환경'이 포함된 CSV 파일을 넣어주세요.")
    else:
        # 날짜 필터링
        filtered_env = env_df.copy()
        if env_dates is not None and start_date is not None and end_date is not None and start_date <= end_date:
            mask = (env_dates >= pd.Timestamp(start_date)) & (
                env_dates <= pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            )
            filtered_env = env_df.loc[mask.fillna(False)].copy()

        if filtered_env.empty:
            st.warning("선택한 날짜 범위 내에 환경 데이터가 없습니다. 날짜 범위를 넓혀보세요.")
        else:
            dt_filtered = get_datetime_series(filtered_env, time_col)

            # 환경 요약 표
            st.subheader("📋 환경 데이터 요약 통계")
            st.caption("표준편차: 값들이 평균에서 얼마나 흩어져 있는지 나타내는 값. 클수록 변동이 큽니다.")
            env_summary_rows = []
            env_metrics = [
                ("온도 (℃)", temp_col, "℃"),
                ("습도 (%)", hum_col, "%"),
                ("EC (dS/m)", ec_col, "dS/m"),
                ("pH", ph_col, ""),
            ]
            for label, col, unit in env_metrics:
                if col is not None and col in filtered_env.columns:
                    stats = describe_stats(filtered_env[col])
                    env_summary_rows.append({
                        "측정 항목": label,
                        "단위": unit,
                        "평균": f"{stats['평균']:.3f}",
                        "표준편차": f"{stats['표준편차']:.3f}",
                        "최소": f"{stats['최소']:.3f}",
                        "최대": f"{stats['최대']:.3f}",
                    })
                else:
                    env_summary_rows.append({
                        "측정 항목": label, "단위": unit,
                        "평균": "—", "표준편차": "—", "최소": "—", "최대": "—",
                    })
            st.table(pd.DataFrame(env_summary_rows))

            st.divider()

            # ── 날짜별 평균 온도·습도 꺾은선 ──
            st.subheader("📅 날짜별 평균 온도·습도 변화")
            if temp_col is not None or hum_col is not None:
                if dt_filtered is not None and dt_filtered.notna().any():
                    agg_dict = {}
                    if temp_col is not None:
                        agg_dict["온도(℃)"] = pd.NamedAgg(column=temp_col, aggfunc="mean")
                    if hum_col is not None:
                        agg_dict["습도(%)"] = pd.NamedAgg(column=hum_col, aggfunc="mean")
                    daily_group = filtered_env.copy()
                    daily_group["date"] = dt_filtered.dt.date
                    daily_group = daily_group.groupby("date").agg(**agg_dict).reset_index()

                    fig_daily = make_subplots(specs=[[{"secondary_y": True}]])
                    if temp_col is not None:
                        fig_daily.add_trace(
                            go.Scatter(x=daily_group["date"], y=daily_group["온도(℃)"],
                                       mode="lines+markers", name="평균 온도 (℃)",
                                       line=dict(color="#e74c3c", width=2)),
                            secondary_y=False,
                        )
                    if hum_col is not None:
                        fig_daily.add_trace(
                            go.Scatter(x=daily_group["date"], y=daily_group["습도(%)"],
                                       mode="lines+markers", name="평균 습도 (%)",
                                       line=dict(color="#3498db", width=2)),
                            secondary_y=True,
                        )
                    fig_daily.update_layout(
                        height=400,
                        xaxis_title="날짜",
                        legend=dict(orientation="h", yanchor="top", y=1.1, xanchor="center", x=0.5),
                        font=PLOT_FONT,
                        margin=dict(t=40, b=40, l=40, r=40),
                    )
                    fig_daily.update_yaxes(title_text="온도 (℃)", secondary_y=False)
                    fig_daily.update_yaxes(title_text="습도 (%)", secondary_y=True)
                    st.plotly_chart(fig_daily, width="stretch")
                else:
                    st.warning("시간 데이터를 파싱할 수 없어 날짜별 그래프를 그릴 수 없습니다.")
            else:
                st.warning("온도·습도 컬럼이 모두 없습니다.")

            st.divider()

            # ── 시간대별 평균 온도·습도 꺾은선 ──
            st.subheader("⏰ 시간대(0~23시)별 평균 온도·습도 변화")
            if temp_col is not None or hum_col is not None:
                if dt_filtered is not None and dt_filtered.notna().any():
                    agg_h = {}
                    if temp_col is not None:
                        agg_h["평균 온도(℃)"] = pd.NamedAgg(column=temp_col, aggfunc="mean")
                    if hum_col is not None:
                        agg_h["평균 습도(%)"] = pd.NamedAgg(column=hum_col, aggfunc="mean")
                    hourly_group = filtered_env.copy()
                    hourly_group["hour"] = dt_filtered.dt.hour
                    hourly_group = hourly_group.groupby("hour").agg(**agg_h).reset_index()

                    hottest_hour = None
                    coldest_hour = None
                    if temp_col is not None:
                        valid = hourly_group.dropna(subset=["평균 온도(℃)"])
                        if not valid.empty:
                            hottest_hour = int(valid.loc[valid["평균 온도(℃)"].idxmax(), "hour"])
                            coldest_hour = int(valid.loc[valid["평균 온도(℃)"].idxmin(), "hour"])

                    fig_hourly = make_subplots(specs=[[{"secondary_y": True}]])
                    if temp_col is not None:
                        fig_hourly.add_trace(
                            go.Scatter(
                                x=hourly_group["hour"], y=hourly_group["평균 온도(℃)"],
                                mode="lines+markers", name="평균 온도 (℃)",
                                line=dict(color="#e74c3c", width=2),
                            ),
                            secondary_y=False,
                        )
                        if hottest_hour is not None:
                            fig_hourly.add_vline(
                                x=hottest_hour, line_dash="dash", line_color="#e67e22", line_width=2,
                                annotation_text=f"가장 더운 시간대: {hottest_hour}시",
                                annotation_position="top",
                            )
                        if coldest_hour is not None:
                            fig_hourly.add_vline(
                                x=coldest_hour, line_dash="dash", line_color="#3498db", line_width=2,
                                annotation_text=f"가장 추운 시간대: {coldest_hour}시",
                                annotation_position="bottom",
                            )
                    if hum_col is not None:
                        fig_hourly.add_trace(
                            go.Scatter(
                                x=hourly_group["hour"], y=hourly_group["평균 습도(%)"],
                                mode="lines+markers", name="평균 습도 (%)",
                                line=dict(color="#3498db", width=2),
                            ),
                            secondary_y=True,
                        )
                    fig_hourly.update_layout(
                        height=400,
                        xaxis_title="시간대 (시)",
                        xaxis=dict(tickmode="linear", tick0=0, dtick=2),
                        legend=dict(orientation="h", yanchor="top", y=1.1, xanchor="center", x=0.5),
                        font=PLOT_FONT,
                        margin=dict(t=40, b=40, l=40, r=40),
                    )
                    fig_hourly.update_yaxes(title_text="온도 (℃)", secondary_y=False)
                    fig_hourly.update_yaxes(title_text="습도 (%)", secondary_y=True)
                    st.plotly_chart(fig_hourly, width="stretch")
                    if hottest_hour is not None and coldest_hour is not None:
                        st.caption(f"📌 가장 더운 시간대 {hottest_hour}시, 가장 추운 시간대 {coldest_hour}시 "
                                   f"(하루 평균 일교차 ≈ {hourly_group['평균 온도(℃)'].max() - hourly_group['평균 온도(℃)'].min():.2f} ℃)")
                else:
                    st.warning("시간 데이터를 파싱할 수 없어 시간대별 그래프를 그릴 수 없습니다.")
            else:
                st.warning("온도·습도 컬럼이 모두 없습니다.")

            st.divider()

            # ── 날짜별 EC·pH 꺾은선 ──
            st.subheader("🧪 날짜별 평균 EC·pH 변화")
            if ec_col is not None or ph_col is not None:
                if dt_filtered is not None and dt_filtered.notna().any():
                    agg_ecph = {}
                    if ec_col is not None:
                        agg_ecph["EC (dS/m)"] = pd.NamedAgg(column=ec_col, aggfunc="mean")
                    if ph_col is not None:
                        agg_ecph["pH"] = pd.NamedAgg(column=ph_col, aggfunc="mean")
                    daily_ecph = filtered_env.copy()
                    daily_ecph["date"] = dt_filtered.dt.date
                    daily_ecph = daily_ecph.groupby("date").agg(**agg_ecph).reset_index()

                    fig_ecph = make_subplots(specs=[[{"secondary_y": True}]])
                    if ec_col is not None:
                        fig_ecph.add_trace(
                            go.Scatter(x=daily_ecph["date"], y=daily_ecph["EC (dS/m)"],
                                       mode="lines+markers", name="평균 EC (dS/m)",
                                       line=dict(color="#2ecc71", width=2)),
                            secondary_y=False,
                        )
                    if ph_col is not None:
                        fig_ecph.add_trace(
                            go.Scatter(x=daily_ecph["date"], y=daily_ecph["pH"],
                                       mode="lines+markers", name="평균 pH",
                                       line=dict(color="#9b59b6", width=2)),
                            secondary_y=True,
                        )
                    fig_ecph.update_layout(
                        height=350,
                        xaxis_title="날짜",
                        legend=dict(orientation="h", yanchor="top", y=1.1, xanchor="center", x=0.5),
                        font=PLOT_FONT,
                        margin=dict(t=40, b=40, l=40, r=40),
                    )
                    fig_ecph.update_yaxes(title_text="EC (dS/m)", secondary_y=False)
                    fig_ecph.update_yaxes(title_text="pH", secondary_y=True)
                    st.plotly_chart(fig_ecph, width="stretch")
                else:
                    st.warning("시간 데이터를 파싱할 수 없어 EC·pH 그래프를 그릴 수 없습니다.")
            else:
                st.info("이 학교 데이터에는 EC·pH 측정값이 없습니다.")

            st.divider()

            # ── 환경 데이터 원본 테이블 + CSV 다운로드 ──
            with st.expander("📄 환경 데이터 원본 테이블 + CSV 다운로드"):
                st.dataframe(filtered_env, width="stretch", height=300)
                csv_bytes = filtered_env.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 CSV 다운로드",
                    data=csv_bytes,
                    file_name="환경데이터_filtered.csv",
                    mime="text/csv",
                )

# ═════════════════════════════════════════════
# TAB 3 — 생육 결과
# ═════════════════════════════════════════════
with tab3:
    st.header("📊 생육 결과")

    if growth_df is None or growth_df.empty:
        st.error("생육 데이터가 없습니다. data/ 폴더에 '생육'이 포함된 CSV 파일을 넣어주세요.")
    else:
        gdf = growth_df.copy()
        for c in [leaf_col, shoot_col, root_col, weight_col]:
            if c is not None:
                gdf[c] = pd.to_numeric(gdf[c], errors="coerce")

        growth_items = [
            ("잎 수", leaf_col, "장"),
            ("지상부 길이", shoot_col, "mm"),
            ("지하부 길이", root_col, "mm"),
            ("생중량", weight_col, "g"),
        ]

        # ── 핵심 결과 카드 ──
        st.subheader("🥇 핵심 결과")
        c1, c2, c3 = st.columns(3)

        if weight_col is not None and id_col is not None:
            valid_w = gdf[[id_col, weight_col]].dropna()
            if not valid_w.empty:
                max_idx = valid_w[weight_col].idxmax()
                min_idx = valid_w[weight_col].idxmin()
                max_val = valid_w.loc[max_idx, weight_col]
                min_val = valid_w.loc[min_idx, weight_col]
                max_id = valid_w.loc[max_idx, id_col]
                min_id = valid_w.loc[min_idx, id_col]
                with c1:
                    st.metric(label="🔺 생중량 최대 개체", value=f"#{max_id} — {max_val:.2f} g")
                with c2:
                    st.metric(label="🔻 생중량 최소 개체", value=f"#{min_id} — {min_val:.2f} g")
                with c3:
                    ratio = (max_val / min_val) if min_val else np.nan
                    st.metric(label="📏 최대/최소 배수",
                              value=f"{ratio:.1f}배" if not np.isnan(ratio) else "—")
            else:
                c1.metric(label="🔺 생중량 최대 개체", value="데이터 없음")
                c2.metric(label="🔻 생중량 최소 개체", value="데이터 없음")
                c3.metric(label="📏 최대/최소 배수", value="데이터 없음")
        else:
            c1.metric(label="🔺 생중량 최대 개체", value="컬럼 없음")
            c2.metric(label="🔻 생중량 최소 개체", value="컬럼 없음")
            c3.metric(label="📏 최대/최소 배수", value="컬럼 없음")

        st.divider()

        # ── 항목별 기초 통계 표 (CV 포함) ──
        st.subheader("📋 항목별 기초 통계")
        st.caption(
            "CV(변동계수) = 표준편차 ÷ 평균 × 100(%). 잎 수(장)와 생중량(g)처럼 단위가 다른 항목끼리 "
            "'개체 간 차이가 얼마나 큰지'를 비교할 때 사용합니다."
        )
        stats_rows = []
        max_cv_item = None
        max_cv_val = -1
        for label, col, unit in growth_items:
            if col is not None and col in gdf.columns:
                stats = describe_stats(gdf[col])
                cv_val = stats["CV(%)"]
                stats_rows.append({
                    "생육 항목": label,
                    "단위": unit,
                    "평균": f"{stats['평균']:.2f}",
                    "중앙값": f"{stats['중앙값']:.2f}",
                    "표준편차": f"{stats['표준편차']:.2f}",
                    "CV(%)": f"{cv_val:.1f}%" if not np.isnan(cv_val) else "—",
                    "최소": f"{stats['최소']:.2f}",
                    "최대": f"{stats['최대']:.2f}",
                    "N": stats["N"],
                })
                if not np.isnan(cv_val) and cv_val > max_cv_val:
                    max_cv_val = cv_val
                    max_cv_item = label
            else:
                stats_rows.append({
                    "생육 항목": label, "단위": unit, "평균": "—", "중앙값": "—",
                    "표준편차": "—", "CV(%)": "—", "최소": "—", "최대": "—", "N": 0,
                })
        st.table(pd.DataFrame(stats_rows))
        if max_cv_item is not None:
            st.info(f"👉 개체 간 차이(CV)가 가장 큰 항목은 **{max_cv_item}** (CV = {max_cv_val:.1f}%) 입니다.")

        st.divider()

        # ── 항목별 평균 ± 표준편차 막대그래프 (2×2 서브플롯) ──
        st.subheader("📊 항목별 평균 ± 표준편차")
        st.caption("막대는 평균, 오차 막대(±표준편차)는 개체 간 변동 폭입니다. 단위가 달라 항목별로 분리했습니다.")
        valid_items = [(l, c, u) for l, c, u in growth_items if c is not None and c in gdf.columns]
        if valid_items:
            n_cols = 2
            n_rows = (len(valid_items) + 1) // 2
            fig_bar = make_subplots(
                rows=n_rows, cols=n_cols,
                subplot_titles=[f"{l} ({u})" for l, c, u in valid_items],
            )
            colors_bar = ["#2ecc71", "#3498db", "#e74c3c", "#9b59b6"]
            for idx, (label, col, unit) in enumerate(valid_items):
                stats = describe_stats(gdf[col])
                row = idx // n_cols + 1
                col_idx = idx % n_cols + 1
                fig_bar.add_trace(
                    go.Bar(
                        x=[label], y=[stats["평균"]],
                        error_y=dict(type="data", array=[stats["표준편차"]], width=8, color="#555555"),
                        marker_color=colors_bar[idx % len(colors_bar)],
                        name=label,
                    ),
                    row=row, col=col_idx,
                )
                fig_bar.update_yaxes(title_text=unit, row=row, col=col_idx)
            fig_bar.update_layout(
                height=500, showlegend=False, font=PLOT_FONT,
                margin=dict(t=40, b=40, l=40, r=40),
            )
            st.plotly_chart(fig_bar, width="stretch")

        st.divider()

        # ── 선택 항목 히스토그램 + 상자그림 ──
        st.subheader(f"📈 선택한 항목: {selected_metric} — 히스토그램 & 상자그림")
        st.caption("히스토그램: 값의 구간별 개체 수. 상자그림(박스플롯): 중앙값·사분위 범위·이상치를 한눈에 보여줍니다.")
        actual_col = find_column(gdf, growth_col_map[selected_metric])
        if actual_col is not None and actual_col in gdf.columns:
            hcol1, hcol2 = st.columns(2)
            with hcol1:
                fig_hist = px.histogram(
                    gdf, x=actual_col, nbins=15,
                    title=f"{selected_metric} 분포 (히스토그램)",
                    color_discrete_sequence=["#2ecc71"],
                )
                fig_hist.update_layout(
                    height=350, xaxis_title=selected_metric, yaxis_title="개체 수",
                    font=PLOT_FONT, margin=dict(t=40, b=40, l=40, r=40),
                )
                st.plotly_chart(fig_hist, width="stretch")
            with hcol2:
                fig_box = px.box(
                    gdf, y=actual_col, points="all",
                    title=f"{selected_metric} 상자그림 (박스플롯)",
                    color_discrete_sequence=["#3498db"],
                )
                fig_box.update_layout(
                    height=350, yaxis_title=selected_metric,
                    font=PLOT_FONT, margin=dict(t=40, b=40, l=40, r=40),
                )
                st.plotly_chart(fig_box, width="stretch")
        else:
            st.warning(f"{selected_metric} 컬럼을 찾을 수 없습니다.")

        st.divider()

        # ── Top 25% vs Bottom 25% 비교 ──
        st.subheader("🏆 생중량 기준 Top 25% vs Bottom 25% 비교")
        st.caption(
            "생중량 상위 25%(잘 자란 그룹)와 하위 25%(덜 자란 그룹)로 나누어 "
            "잎 수·지상부 길이·지하부 길이의 평균을 비교합니다."
        )
        compare_cols = [c for c in [leaf_col, shoot_col, root_col] if c is not None]
        if weight_col is not None and compare_cols:
            valid_g = gdf[[weight_col] + compare_cols].dropna(subset=[weight_col])
            if len(valid_g) >= 4:
                q75 = valid_g[weight_col].quantile(0.75)
                q25 = valid_g[weight_col].quantile(0.25)
                top_g = valid_g[valid_g[weight_col] >= q75]
                bottom_g = valid_g[valid_g[weight_col] <= q25]
                n_top, n_bottom = len(top_g), len(bottom_g)

                if n_top > 0 and n_bottom > 0:
                    label_map = {leaf_col: "잎 수 (장)", shoot_col: "지상부 길이 (mm)", root_col: "지하부 길이 (mm)"}
                    rows = []
                    for c in compare_cols:
                        rows.append({"그룹": f"Top 25% (잘 자람, n={n_top})", "생육 항목": label_map[c], "평균값": top_g[c].mean()})
                        rows.append({"그룹": f"Bottom 25% (덜 자람, n={n_bottom})", "생육 항목": label_map[c], "평균값": bottom_g[c].mean()})
                    comp_df = pd.DataFrame(rows)

                    fig_comp = px.bar(
                        comp_df, x="생육 항목", y="평균값", color="그룹", barmode="group",
                        title="Top 25% vs Bottom 25% 생육 항목 평균 비교",
                        color_discrete_sequence=["#2ecc71", "#e74c3c"],
                        text_auto=".1f",
                    )
                    fig_comp.update_layout(
                        height=400, xaxis_title="생육 항목", yaxis_title="평균값",
                        legend=dict(orientation="h", yanchor="top", y=1.12, xanchor="center", x=0.5),
                        font=PLOT_FONT, margin=dict(t=60, b=40, l=40, r=40),
                    )
                    st.plotly_chart(fig_comp, width="stretch")

                    st.caption(f"🧑‍🔬 Top 25%: **{n_top}개체** | Bottom 25%: **{n_bottom}개체**")
                    if n_top < 5 or n_bottom < 5:
                        st.caption(
                            f"⚠️ 그룹별 개체 수가 적습니다 (Top {n_top}, Bottom {n_bottom}). "
                            "두 그룹의 차이는 참고용이며, 개체가 몇 개만 달라져도 결과가 바뀔 수 있습니다."
                        )
                else:
                    st.warning("Top 25% 또는 Bottom 25% 그룹이 비어 있습니다.")
            else:
                st.warning(f"유효한 데이터가 {len(valid_g)}개체뿐입니다. 최소 4개체 이상이 필요합니다.")
        else:
            st.warning("생중량 또는 비교할 생육 항목 컬럼이 없어 Top/Bottom 25% 비교를 수행할 수 없습니다.")

        st.divider()

        # ── 산점도: 잎 수 vs 생중량 / 지상부 길이 vs 생중량 ──
        st.subheader("🔗 상관관계 분석: 산점도")
        st.caption(
            "상관계수 r은 −1~+1 사이 값으로, +1에 가까울수록 두 항목이 함께 커지는 관계가 강합니다. "
            "관계가 있다는 뜻이지 원인과 결과라는 뜻은 아닙니다."
        )
        scatter_pairs = []
        if leaf_col is not None and weight_col is not None:
            scatter_pairs.append(("잎 수 vs 생중량", leaf_col, weight_col, "잎 수 (장)"))
        if shoot_col is not None and weight_col is not None:
            scatter_pairs.append(("지상부 길이 vs 생중량", shoot_col, weight_col, "지상부 길이 (mm)"))

        if scatter_pairs:
            sc_cols = st.columns(len(scatter_pairs))
            for i, (title, x_col, y_col, x_label) in enumerate(scatter_pairs):
                with sc_cols[i]:
                    valid_scatter = gdf[[x_col, y_col]].dropna()
                    if len(valid_scatter) >= 3:
                        corr_val = valid_scatter[x_col].corr(valid_scatter[y_col])
                        # 추세선: statsmodels 없이 numpy 최소제곱으로 계산
                        slope, intercept = np.polyfit(valid_scatter[x_col], valid_scatter[y_col], 1)
                        x_line = np.linspace(valid_scatter[x_col].min(), valid_scatter[x_col].max(), 50)
                        fig_scatter = go.Figure()
                        fig_scatter.add_trace(go.Scatter(
                            x=valid_scatter[x_col], y=valid_scatter[y_col],
                            mode="markers", name="개체", marker=dict(color="#2ecc71", size=9),
                        ))
                        fig_scatter.add_trace(go.Scatter(
                            x=x_line, y=slope * x_line + intercept,
                            mode="lines", name="추세선", line=dict(color="#e67e22", dash="dash"),
                        ))
                        fig_scatter.update_layout(
                            height=350, title=f"{title} (r = {corr_val:.3f})",
                            xaxis_title=x_label, yaxis_title="생중량 (g)",
                            font=PLOT_FONT, margin=dict(t=50, b=40, l=40, r=40),
                            legend=dict(orientation="h", yanchor="top", y=1.15, xanchor="center", x=0.5),
                        )
                        st.plotly_chart(fig_scatter, width="stretch")
                        st.caption(f"📌 {title} — 상관계수 r = {corr_val:.3f}")
                    else:
                        st.warning(f"{title} 그래프를 그리기에 데이터가 부족합니다.")
        else:
            st.warning("산점도를 그릴 생육 항목 조합이 없습니다.")

        st.divider()

        # ── 생육 결과 원본 테이블 + CSV 다운로드 ──
        with st.expander("📄 생육 결과 원본 테이블 + CSV 다운로드"):
            st.dataframe(growth_df, width="stretch", height=300)
            csv_bytes_g = growth_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 CSV 다운로드",
                data=csv_bytes_g,
                file_name="생육결과데이터.csv",
                mime="text/csv",
            )
