import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io, hashlib

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(page_title="극지식물 생육 분석 대시보드", layout="wide")

# ─────────────────────────────────────────────
# 한글 폰트 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 캐싱 로더 (BytesIO 해시 키로 중복 로딩 방지)
# ─────────────────────────────────────────────
def _bytesio_hash(b):
    return hashlib.md5(b.getvalue()).hexdigest()

@st.cache_data(hash_funcs={io.BytesIO: _bytesio_hash})
def _read_csv_cached(file_bytes, encoding):
    return pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)

# ✦✦✦ 수정된 부분: def 뒤 괄호 추가 ✦✦✦
def load_csv_fallback(uploaded_file):
    """utf-8-sig 우선, 실패 시 cp949 fallback"""
    if uploaded_file is None:
        return None
    raw = uploaded_file.read()          # BytesIO → bytes
    try:
        return _read_csv_cached(raw, 'utf-8-sig')
    except Exception:
        try:
            return _read_csv_cached(raw, 'cp949')
        except Exception:
            return None

def extract_school_name(filename: str) -> str:
    """파일명에서 학교명 추출 (예: 인천여고_환경데이터.csv → 인천여고)"""
    if not filename:
        return "우리 학교"
    base = filename.replace('.csv', '')
    for suf in ['_환경데이터', '_생육결과데이터', '_환경', '_생육']:
        if base.endswith(suf):
            return base[: -len(suf)]
    return base

def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan

def _fmt_num(v, d=1):
    if pd.isna(v):
        return "–"
    return f"{v:,.{d}f}"

# ─────────────────────────────────────────────
# 사이드바: 파일 업로드
# ─────────────────────────────────────────────
st.sidebar.title("📂 데이터 업로드")

env_file = st.sidebar.file_uploader(
    "환경 데이터 CSV",
    type=["csv"],
    help="시간, 온도, 습도, pH, EC 등 환경 측정값 (열 이름은 학교마다 다를 수 있음)",
)

growth_file = st.sidebar.file_uploader(
    "생육 결과 데이터 CSV",
    type=["csv"],
    help="개체번호, 잎 수, 길이, 질량 등 생육 측정값 (열 이름은 학교마다 다를 수 있음)",
)

st.sidebar.markdown("---")
st.sidebar.subheader("📏 생육 측정 항목 선택")
st.sidebar.info(
    "아래 체크박스에서 그래프에 표시할 항목을 고르세요.\n"
    "기본적으로 생중량이 선택되어 있습니다."
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "💡 인코딩 팁: 인코딩 오류가 나면 Streamlit이 자동으로 cp949로 재시도합니다.\n"
    "CSV를 열 때 'UTF-8 with BOM'으로 저장하면 가장 안정적입니다."
)

# 파일명 기반 학교명 추출
env_school = extract_school_name(env_file.name) if env_file else None
grt_school = extract_school_name(growth_file.name) if growth_file else None
school_name = env_school or grt_school or "우리 학교"

# ─────────────────────────────────────────────
# 데이터 로딩 (스핀너 + @st.cache_data)
# ─────────────────────────────────────────────
with st.spinner("환경 데이터를 읽고 있습니다…"):
    df_env = load_csv_fallback(env_file)

with st.spinner("생육 결과 데이터를 읽고 있습니다…"):
    df_grt = load_csv_fallback(growth_file)

# 데이터 로딩 실패 안내 (탭 안에서 st.stop() 사용 금지 → 최상위에서만 조건부 분기)
env_err = df_env is None and env_file is not None
grt_err = df_grt is None and growth_file is not None

if env_err:
    st.error("⛔ 환경 CSV 파일을 읽는 중 오류가 발생했습니다.\n"
             "인코딩(utf-8-sig 또는 cp949)을 확인하거나, CSV를 다시 업로드해 주세요.")
if grt_err:
    st.error("⛔ 생육 CSV 파일을 읽는 중 오류가 발생했습니다.\n"
             "인코딩(utf-8-sig 또는 cp949)을 확인하거나, CSV를 다시 업로드해 주세요.")

# ─────────────────────────────────────────────
# 탭 구조
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📖 실험 개요",
    "🌡️ 환경 데이터",
    "📊 생육 결과",
])

# ─────────────────────────────────────────────
# 공통 통계 용어 설명 (고등학생 대상)
# ─────────────────────────────────────────────
TERM_MEAN   = ("📌 평균(mean): 모든 값을 더해 개수로 나눈 값. "
               "자료의 '대표값'으로 자주 씁니다.")
TERM_STD    = ("📌 표준편차(std): 값들이 평균에서 얼마나 떨어져 있는지 나타내는 지표. "
               "수치가 클수록 개체 간 차이가 큽니다.")
TERM_CV     = ("📌 변동계수(CV, coefficient of variation): "
               "표준편차를 평균으로 나눈 값(% 단위). "
               "평균이 다른 항목끼리도 변동성을 비교할 수 있습니다.")
TERM_CORR   = ("📌 상관계수(r, correlation coefficient): "
               "두 변수가 함께 움직이는 정도를 -1 ~ +1 사이 숫자로 나타낸 값. "
               "1에 가까울수록 함께 증가하고, -1에 가까울수록 반대로 움직입니다. "
               "0에 가까우면 뚜렷한 선형 관계가 없습니다.")

# ─────────────────────────────────────────────
# Tab 1 — 실험 개요
# ─────────────────────────────────────────────
with tab1:
    st.markdown(f"## 🌱 {school_name} 극지식물 개체별 생육 차이 분석")

    st.markdown(
        "### 연구 배경 및 목적\n"
        "극지환경(한랭·건조·낮은 영양)을 모사한 조건에서 식물을 재배할 때, "
        "같은 환경이라도 **개체마다 생육 결과가 다르게 나타납니다.**\n\n"
        "이 대시보드는 우리 학교 극지식물 실험에서 얻은 "
        "**개체별 생육 데이터**와 **환경 데이터**를 한눈에 비교하고, "
        "생중량(생물체 전체 무게)을 중심으로 개체 간 차이가 얼마나 큰지, "
        "잎 수·길이 같은 측정 항목과 생중량이 어떤 관계에 있는지 살펴보는 도구입니다.\n\n"
        "✏️ **통계 용어 미리 보기**\n"
        f"- {TERM_MEAN}\n"
        f"- {TERM_STD}\n"
        f"- {TERM_CV}\n"
        f"- {TERM_CORR}"
    )

    # ── 데이터가 있을 때만 요약 표 & 카드 표시 ──
    has_any = (df_env is not None) or (df_grt is not None)
    if not has_any:
        st.info("📎 사이드바에서 CSV 파일을 업로드하면 여기에 실험 개요와 지표가 표시됩니다.")
    else:
        # 데이터 요약 표
        st.markdown("### 📋 데이터 요약")
        summary_rows = []

        if df_env is not None:
            env_cols = list(df_env.columns)
            env_dates = pd.to_datetime(df_env['time'], errors='coerce').dropna()
            env_start = env_dates.min().strftime('%Y-%m-%d') if len(env_dates) else "–"
            env_end   = env_dates.max().strftime('%Y-%m-%d') if len(env_dates) else "–"
            env_ndays = (env_dates.dt.date.nunique()) if len(env_dates) else 0
            summary_rows.append(("환경 데이터", f"{len(df_env):,}행",
                                 f"측정 기간: {env_start} ~ {env_end} ({env_ndays}일)",
                                 ", ".join(env_cols)))
        else:
            summary_rows.append(("환경 데이터", "업로드되지 않음", "–", "–"))

        if df_grt is not None:
            grt_cols = list(df_grt.columns)
            summary_rows.append(("생육 결과 데이터", f"{len(df_grt):,}개체",
                                 "1회 측정 (개체별)", ", ".join(grt_cols)))
        else:
            summary_rows.append(("생육 결과 데이터", "업로드되지 않음", "–", "–"))

        st.table(
            pd.DataFrame(summary_rows, columns=["데이터", "크기", "기간 / 방식", "컬럼"])
        )

        # ── 주요 지표 카드 4개: 총 개체수, 평균 온도, 평균 습도, 평균 생중량 ──
        st.markdown("### 📊 주요 지표")
        c1, c2, c3, c4 = st.columns(4)

        n_total = len(df_grt) if df_grt is not None else 0
        c1.metric("총 개체 수", f"{n_total}개체", delta=None, delta_color="off")

        if df_env is not None and 'temperature' in df_env.columns:
            t_mean = df_env['temperature'].mean()
            c2.metric("평균 온도", f"{t_mean:.1f} ℃", delta=None, delta_color="off")
        else:
            c2.metric("평균 온도", "데이터 없음", delta=None, delta_color="off")

        if df_env is not None and 'humidity' in df_env.columns:
            h_mean = df_env['humidity'].mean()
            c3.metric("평균 습도", f"{h_mean:.1f} %", delta=None, delta_color="off")
        else:
            c3.metric("평균 습도", "데이터 없음", delta=None, delta_color="off")

        if df_grt is not None and '생중량(g)' in df_grt.columns:
            gw_mean = df_grt['생중량(g)'].mean()
            c4.metric("평균 생중량", f"{gw_mean:.2f} g", delta=None, delta_color="off")
        else:
            c4.metric("평균 생중량", "데이터 없음", delta=None, delta_color="off")

        st.caption(
            "▲ 평균 생중량은 개체별 생중량(g)의 산술평균입니다. "
            "표준편차와 변동계수(CV)는 Tab 3에서 확인할 수 있습니다."
        )

# ─────────────────────────────────────────────
# Tab 2 — 환경 데이터
# ─────────────────────────────────────────────
with tab2:
    if env_err:
        st.warning("⚠️ 환경 CSV 파일을 읽을 수 없습니다. 사이드바에서 파일을 다시 업로드해 주세요.")
        st.stop()

    if df_env is None:
        st.info("📎 사이드바에서 **환경 데이터 CSV**를 업로드하면 환경 데이터 탭이 활성화됩니다.")
    else:
        has_temp = 'temperature' in df_env.columns
        has_hum  = 'humidity'  in df_env.columns
        has_ph   = 'ph'        in df_env.columns
        has_ec   = 'ec'        in df_env.columns
        has_wt   = 'water_temp' in df_env.columns
        has_co2  = 'co2'       in df_env.columns

        time_col = 'time' if 'time' in df_env.columns else df_env.columns[0]
        df_env[time_col] = pd.to_datetime(df_env[time_col], errors='coerce')
        df_env['date'] = df_env[time_col].dt.date

        # ── 환경 요약 표 ──
        st.markdown("### 🌡️ 환경 요약 (평균 · 최소 · 최대)")
        summary_env = {}
        for col, label, unit in [
            ('temperature', '온도', '℃'),
            ('humidity',    '습도', '%'),
            ('ph',          'pH',   ''),
            ('ec',          'EC',   'mS/cm'),
            ('water_temp',  '수온', '℃'),
            ('co2',         'CO₂',  'ppm'),
        ]:
            if col in df_env.columns:
                s = df_env[col].dropna()
                summary_env[label] = {
                    '평균': f"{s.mean():.2f}{unit}",
                    '최소': f"{s.min():.2f}{unit}",
                    '최대': f"{s.max():.2f}{unit}",
                    '측정 횟수': f"{len(s):,}",
                }

        if summary_env:
            st.table(pd.DataFrame(summary_env).T)
        else:
            st.warning("⚠️ 인식할 수 있는 환경 열(temperature, humidity, ph, ec, water_temp, co2)이 없습니다.")

        st.caption(
            f"▲ {TERM_MEAN}  ▲ {TERM_STD} (최소·최대는 전체 기간 중 가장 작은/큰 값)"
        )

        # ── 날짜별 일별 평균 시계열 ──
        st.markdown("### 📈 날짜별 일별 평균")
        daily = df_env.groupby('date').mean(numeric_only=True).reset_index()
        daily['date'] = pd.to_datetime(daily['date'])

        n_plots = sum([has_temp, has_hum, has_ph, has_ec, has_wt, has_co2])
        if n_plots > 0:
            fig_env = make_subplots(
                rows=n_plots, cols=1,
                shared_xaxes=True,
                subplot_titles=[
                    "온도 변화" if has_temp else None,
                    "습도 변화" if has_hum else None,
                    "pH 변화" if has_ph else None,
                    "EC 변화" if has_ec else None,
                    "수온 변화" if has_wt else None,
                    "CO₂ 변화" if has_co2 else None,
                ],
                vertical_spacing=0.08,
            )
            colors = dict(
                temperature='#ff6b6b', humidity='#4ecdc4',
                ph='#a8e6cf', ec='#ffd93d', water_temp='#6c5ce7', co2='#fd79a8'
            )
            row_i = 1
            for col, label, unit, color in [
                ('temperature', '온도', '℃', colors['temperature']),
                ('humidity',    '습도', '%',  colors['humidity']),
                ('ph',          'pH',   '',   colors['ph']),
                ('ec',          'EC',   'mS/cm', colors['ec']),
                ('water_temp',  '수온', '℃',  colors['water_temp']),
                ('co2',         'CO₂',  'ppm', colors['co2']),
            ]:
                if col in df_env.columns and col in daily.columns:
                    y_vals = daily[col].astype(float)
                    fig_env.add_trace(
                        go.Scatter(
                            x=daily['date'], y=y_vals,
                            mode='lines+markers',
                            name=label, line=dict(color=color, width=2),
                            marker=dict(size=3),
                            hovertemplate=f"{label}: %{{y:.2f}}{unit}<extra></extra>",
                        ),
                        row=row_i, col=1,
                    )
                    row_i += 1

            fig_env.update_layout(
                height=max(200, n_plots * 160),
                margin=dict(l=40, r=20, t=40, b=40),
                font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
                showlegend=True,
                hovermode='x unified',
                xaxis=dict(tickformat='%m/%d', showgrid=True, gridcolor='#e0e0e0'),
            )
            st.plotly_chart(fig_env, key="env_timeseries", width='stretch')
        else:
            st.warning("⚠️ 환경 데이터에서 그래프로 그릴 열을 찾을 수 없습니다. (temperature, humidity 등 필요)")

        # ── Expander: 원본 테이블 + CSV 다운로드 ──
        with st.expander("📋 환경 데이터 원본 테이블 + CSV 다운로드", expanded=False):
            st.dataframe(df_env.drop(columns=['date'], errors='ignore'),
                        use_container_width=True)
            csv_bytes = df_env.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="⬇️ 환경 데이터 CSV 다운로드",
                data=csv_bytes,
                file_name=f"{school_name}_환경데이터.csv",
                mime="text/csv",
            )

# ─────────────────────────────────────────────
# Tab 3 — 생육 결과
# ─────────────────────────────────────────────
with tab3:
    if grt_err:
        st.warning("⚠️ 생육 CSV 파일을 읽을 수 없습니다. 사이드바에서 파일을 다시 업로드해 주세요.")
        st.stop()

    if df_grt is None:
        st.info("📎 사이드바에서 **생육 결과 데이터 CSV**를 업로드하면 생육 결과 탭이 활성화됩니다.")
    else:
        ALL_COLS  = list(df_grt.columns)
        ID_COL    = '개체번호' if '개체번호' in ALL_COLS else None
        MEAS_COLS = [c for c in ALL_COLS if c != ID_COL]
        GW_COL    = '생중량(g)' if '생중량(g)' in ALL_COLS else None

        if 'selected_measure' not in st.session_state:
            st.session_state.selected_measure = [GW_COL] if GW_COL else MEAS_COLS[:1]

        st.sidebar.markdown("---")
        st.sidebar.subheader("📏 생육 측정 항목 선택 (Tab 3 막대 그래프)")
        available_measure = [c for c in MEAS_COLS if c != ID_COL]
        default_m = [GW_COL] if GW_COL and GW_COL in available_measure else (available_measure[:1] if available_measure else [])
        selected_m = st.sidebar.multiselect(
            "그래프에 표시할 측정 항목",
            options=available_measure,
            default=default_m,
            help="비교하고 싶은 생육 측정 항목을 선택하세요. 생중량은 기본 선택됩니다.",
        )
        st.session_state.selected_measure = selected_m

        # ── 핵심 결과 카드 ──
        st.markdown("### 🥇 핵심 결과 카드")
        gc1, gc2, gc3 = st.columns(3)

        if GW_COL and '생중량(g)' in df_grt.columns:
            gw = df_grt['생중량(g)'].dropna()
            gw_mean = gw.mean()
            gw_max  = gw.max()
            gw_min  = gw.min()

            max_row = df_grt.loc[gw.idxmax()]
            max_id  = max_row[ID_COL] if ID_COL else "–"
            min_row = df_grt.loc[gw.idxmin()]
            min_id  = min_row[ID_COL] if ID_COL else "–"

            gc1.metric("평균 생중량", f"{gw_mean:.2f} g", delta=None, delta_color="off")
            gc2.metric("최대 생중량", f"{gw_max:.2f} g",
                       delta=f"개체번호 {max_id}", delta_color="normal")
            gc3.metric("최소 생중량", f"{gw_min:.2f} g",
                       delta=f"개체번호 {min_id}", delta_color="normal")
        else:
            st.warning("⚠️ '생중량(g)' 열을 찾을 수 없습니다. CSV 컬럼 이름을 확인해 주세요.")

        st.caption(
            f"▲ {TERM_MEAN}  ▲ {TERM_STD}  "
            "생중량 상위 25% / 하위 25% 비교는 아래 분포도에서 확인할 수 있습니다."
        )

        # ── 개체별 생육 비교 (막대 그래프) ──
        st.markdown("### 📊 개체별 생육 비교 (막대 그래프)")
        if selected_m:
            plot_df = df_grt[selected_m].copy()
            plot_df.index = range(1, len(plot_df) + 1)
            plot_df.index.name = '개체'

            fig_bar = px.bar(
                plot_df,
                x=plot_df.index,
                y=selected_m,
                barmode='group',
                color_discrete_sequence=px.colors.qualitative.Set2,
                labels={'variable': '측정 항목', 'value': '측정값', 'x': '개체 번호'},
                hover_data={'x': False},
            )
            fig_bar.update_layout(
                height=max(300, 180 + 40 * len(selected_m)),
                font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
                xaxis_title="개체 번호 (1번부터)",
                yaxis_title="측정값",
                xaxis=dict(tickangle=0, showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
                barmode='group',
            )
            st.plotly_chart(fig_bar, key="growth_bar", width='stretch')
        else:
            st.warning("⚠️ 표시할 측정 항목을 선택해 주세요. (사이드바에서 선택)")

        # ── 평균 지표 카드 ──
        st.markdown("### 📐 평균 생육 지표")
        avg_cols = ['잎 수(장)', '지상부 길이(mm)', '지하부길이(mm)',
                    '생중량(g)', '지상부질량(g)', '지하부질량(g)']
        avail_avg = [c for c in avg_cols if c in df_grt.columns]

        if avail_avg:
            avg_data = {c: df_grt[c].mean() for c in avail_avg}
            unit_map = {
                '잎 수(장)': '장', '지상부 길이(mm)': 'mm', '지하부길이(mm)': 'mm',
                '생중량(g)': 'g', '지상부질량(g)': 'g', '지하부질량(g)': 'g',
            }
            rows = [
                {"측정 항목": c, "평균": f"{avg_data[c]:.2f}", "단위": unit_map.get(c, '')}
                for c in avail_avg
            ]
            st.table(pd.DataFrame(rows))
            st.caption(f"▲ {TERM_MEAN} — 각 항목별로 모든 개체의 값을 더해 개수로 나눈 값입니다.")
        else:
            st.warning("⚠️ 표시할 생육 측정 열이 없습니다.")

        # ── 생중량 분포 (박스플롯) ──
        st.markdown("### 📦 생중량 분포 (박스플롯)")
        if GW_COL and GW_COL in df_grt.columns:
            gw_data = df_grt[GW_COL].dropna()

            q25 = gw_data.quantile(0.25)
            q75 = gw_data.quantile(0.75)

            fig_box = px.box(
                x=[GW_COL] * len(gw_data),
                y=gw_data.values,
                labels={'x': '생중량(g)', 'y': '생중량(g)'},
                boxmean=True,
            )
            fig_box.update_traces(
                marker_color='#4ecdc4',
                marker=dict(size=4),
                line_color='#1a535c',
            )
            fig_box.add_hline(y=q75, line_dash="dot", line_color='#ff6b6b',
                              annotation_text=f"상위 25% 기준: {q75:.2f} g",
                              annotation_position="top right",
                              annotation_font=dict(size=11, color='#ff6b6b'))
            fig_box.add_hline(y=q25, line_dash="dot", line_color='#6c5ce7',
                              annotation_text=f"하위 25% 기준: {q25:.2f} g",
                              annotation_position="bottom right",
                              annotation_font=dict(size=11, color='#6c5ce7'))
            fig_box.update_layout(
                height=360,
                margin=dict(l=40, r=60, t=30, b=40),
                font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
                xaxis=dict(showticklabels=False),
                yaxis=dict(title='생중량 (g)', showgrid=True, gridcolor='#f0f0f0'),
                showlegend=False,
            )
            st.plotly_chart(fig_box, key="growth_box", width='stretch')

            iqr = q75 - q25
            cv_gw = (gw_data.std() / gw_data.mean() * 100) if gw_data.mean() else float('nan')
            st.markdown(
                f"**생중량 분포 요약**\n"
                f"- 개체 수: {len(gw_data)}개체\n"
                f"- 1사분위(Q1, 하위 25% 기준): **{q25:.2f} g**\n"
                f"- 3사분위(Q3, 상위 25% 기준): **{q75:.2f} g**\n"
                f"- 사분위범위(IQR): {iqr:.2f} g\n"
                f"- 변동계수(CV): **{cv_gw:.1f}%** {TERM_CV}\n"
                f"\n"
                f"💡 붉은 점선(상위 25% 기준) 이상 개체가 상위 25%, "
                f"보라 점선(하위 25% 기준) 이하 개체가 하위 25%입니다."
            )
        else:
            st.warning("⚠️ '생중량(g)' 열이 없어 분포도를 표시할 수 없습니다.")

        # ── 상관관계 분석 (산점도 2개) ──
        st.markdown("### 🔗 상관관계 분석 (산점도)")
        corr_pairs = [
            ('잎 수(장)',     '생중량(g)',  '잎 수(장)',    '생중량 (g)'),
            ('지상부 길이(mm)', '생중량(g)', '지상부 길이 (mm)', '생중량 (g)'),
        ]

        valid_pairs = [(x, y, xl, yl) for x, y, xl, yl in corr_pairs
                       if x in df_grt.columns and y in df_grt.columns]
        n_corr = len(valid_pairs)

        if n_corr > 0:
            fig_corr = make_subplots(
                rows=n_corr, cols=1,
                shared_xaxes=False,
                subplot_titles=[f"{xl} vs 생중량" for _, _, xl, _ in valid_pairs],
                vertical_spacing=0.12,
            )

            row_i = 1
            for x_col, y_col, x_label, y_label in valid_pairs:
                sub = df_grt[[x_col, y_col]].dropna()
                r_val = sub[x_col].corr(sub[y_col])

                fig_corr.add_trace(
                    go.Scatter(
                        x=sub[x_col], y=sub[y_col],
                        mode='markers',
                        marker=dict(
                            size=8, color='#4ecdc4',
                            line=dict(width=1, color='white'),
                            opacity=0.85,
                        ),
                        hovertemplate=f"{x_label}: %{{x:.1f}}<br>{y_label}: %{{y:.2f}}<extra></extra>",
                    ),
                    row=row_i, col=1,
                )

                # 추세선 직접 그리기 (px.scatter trendline 사용 금지)
                z = np.polyfit(sub[x_col], sub[y_col], 1)
                p = np.poly1d(z)
                x_line = np.linspace(sub[x_col].min(), sub[x_col].max(), 100)
                fig_corr.add_trace(
                    go.Scatter(
                        x=x_line, y=p(x_line),
                        mode='lines',
                        line=dict(color='#ff6b6b', width=2, dash='dash'),
                        name=f"추세선 (r={r_val:.2f})",
                        showlegend=False,
                    ),
                    row=row_i, col=1,
                )

                fig_corr.add_annotation(
                    x=0.95, y=0.05, xref='paper', yref='paper',
                    text=f"r = {r_val:.3f}",
                    font=dict(size=13, color='#2d3436',
                              family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                    bgcolor='#ffffffcc',
                    bordercolor='#b2bec3',
                    borderwidth=1,
                    borderpad=4,
                    showarrow=False,
                    row=row_i, col=1,
                )
                row_i += 1

            fig_corr.update_layout(
                height=320 + 220 * n_corr,
                margin=dict(l=40, r=20, t=40, b=40),
                font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
                showlegend=False,
            )
            for i, (_, _, x_label, y_label) in enumerate(valid_pairs):
                fig_corr.update_xaxes(
                    title_text=x_label,
                    showgrid=True, gridcolor='#f0f0f0', row=i + 1, col=1,
                )
                fig_corr.update_yaxes(
                    title_text=y_label,
                    showgrid=True, gridcolor='#f0f0f0', row=i + 1, col=1,
                )
            st.plotly_chart(fig_corr, key="growth_corr", width='stretch')

            st.caption(
                f"▲ {TERM_CORR}\n"
                "빨간 점선은 선형 추세선으로, 두 변수의 경향을 직관적으로 보여줍니다. "
                "r 값이 0.7 이상이면 강한 양의 상관관계, 0.3~0.7은 중간, 0.3 미만은 약한 관계로 해석합니다."
            )
        else:
            st.warning("⚠️ 상관계수 분석에 필요한 열(잎 수, 지상부 길이, 생중량 등)이 없습니다.")

        # ── Expander: 생육 원본 테이블 + CSV 다운로드 ──
        with st.expander("📋 생육 결과 데이터 원본 테이블 + CSV 다운로드", expanded=False):
            st.dataframe(df_grt, use_container_width=True)
            csv_bytes = df_grt.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="⬇️ 생육 결과 데이터 CSV 다운로드",
                data=csv_bytes,
                file_name=f"{school_name}_생육결과데이터.csv",
                mime="text/csv",
            )

# ─────────────────────────────────────────────
# 하단 안내
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    "🌱 본 대시보드는 교육용으로 제작되었습니다. "
    "통계 수치는 업로드된 CSV 데이터에 따라 실시간으로 계산되며, "
    "모든 그래프는 Plotly + Streamlit으로 렌더링됩니다. "
    "Streamlit Cloud에서도 동일한 코드로 실행됩니다."
)
