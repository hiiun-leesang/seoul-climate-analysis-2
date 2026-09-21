# app.py
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# 1. 데이터 로드 및 전처리
# ---------------------------------------------------------------------------
@st.cache_data
def load_data(path: str = "seoul_temperature.csv") -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}\n"
                                f"현재 작업 디렉터리: {os.getcwd()}\n"
                                f"저장소 루트에 '{path}' 파일이 있는지 확인하세요.")

    df = pd.read_csv(path, encoding="utf-8")

    if "날짜" in df.columns:
        df["날짜"] = df["날짜"].astype(str).str.strip("\t")

    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df["연도"] = df["날짜"].dt.year
    df["월"] = df["날짜"].dt.month

    for col in ["평균기온(℃)", "최저기온(℃)", "최고기온(℃)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "최고기온(℃)" in df.columns and "최저기온(℃)" in df.columns:
        df["일교차"] = df["최고기온(℃)"] - df["최저기온(℃)"]

    return df


try:
    df = load_data()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

if df.empty or "연도" not in df.columns:
    st.error("데이터 파일이 비어 있거나 필요한 컬럼이 없습니다.")
    st.stop()

# ---------------------------------------------------------------------------
# 2. 사이드바: 연도 범위 슬라이더
# ---------------------------------------------------------------------------
st.sidebar.title("설정")

min_year = int(df["연도"].min())
max_year = int(df["연도"].max())

year_range = st.sidebar.slider(
    "연도 범위",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
    step=1,
)

start_year, end_year = year_range

# ---------------------------------------------------------------------------
# 3. 연도별 집계
# ---------------------------------------------------------------------------
yearly = (
    df.dropna(subset=["연도"])
    .groupby("연도")
    .agg(
        평균기온=("평균기온(℃)", "mean"),
        최저기온=("최저기온(℃)", "min"),
        최고기온=("최고기온(℃)", "max"),
        평균일교차=("일교차", "mean"),
    )
    .reset_index()
)

yearly["5년 이동평균"] = yearly["평균기온"].rolling(window=5, min_periods=1).mean()

# ---------------------------------------------------------------------------
# 4. 선택 구간 필터링
# ---------------------------------------------------------------------------
mask = (yearly["연도"] >= start_year) & (yearly["연도"] <= end_year)
selected = yearly[mask]

# ---------------------------------------------------------------------------
# 5. 선택 구간 통계 표시
# ---------------------------------------------------------------------------
st.header(f"서울 기온 분석 ({start_year}년 ~ {end_year}년)")

if selected.empty:
    st.warning("선택한 연도에 데이터가 없습니다. 연도 범위를 넓혀주세요.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("평균기온", f"{selected['평균기온'].mean():.1f} ℃")
    col2.metric("최고기온", f"{selected['최고기온'].max():.1f} ℃")
    col3.metric("최저기온", f"{selected['최저기온'].min():.1f} ℃")
    col4.metric("평균 일교차", f"{selected['평균일교차'].mean():.1f} ℃")

# ---------------------------------------------------------------------------
# 6. 월별 히트맵 (Plotly)
# ---------------------------------------------------------------------------
heatmap_data = (
    df.dropna(subset=["연도", "월"])
    .groupby(["연도", "월"])["평균기온(℃)"]
    .mean()
    .unstack(fill_value=None)
)

fig_heatmap = go.Figure(
    data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale="RdYlBu_r",
        hoverongaps=False,
        colorbar=dict(title="평균기온 (℃)"),
    )
)

fig_heatmap.update_layout(
    title="월별 평균기온 히트맵",
    xaxis_title="월",
    yaxis_title="연도",
    height=500,
)

st.plotly_chart(fig_heatmap, use_container_width=True)

# ---------------------------------------------------------------------------
# 7. 최고기온 상위 10일 / 최저기온 하위 10일
# ---------------------------------------------------------------------------
col_top, col_bottom = st.columns(2)

top10_high = (
    df.dropna(subset=["최고기온(℃)"])
    .nlargest(10, "최고기온(℃)")
    [["날짜", "최고기온(℃)"]]
    .reset_index(drop=True)
)
top10_high["날짜"] = top10_high["날짜"].dt.strftime("%Y-%m-%d")

with col_top:
    st.subheader("최고기온 상위 10일")
    st.dataframe(top10_high, use_container_width=True, hide_index=True)

bottom10_low = (
    df.dropna(subset=["최저기온(℃)"])
    .nsmallest(10, "최저기온(℃)")
    [["날짜", "최저기온(℃)"]]
    .reset_index(drop=True)
)
bottom10_low["날짜"] = bottom10_low["날짜"].dt.strftime("%Y-%m-%d")

with col_bottom:
    st.subheader("최저기온 하위 10일")
    st.dataframe(bottom10_low, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# 8. 연도별 평균기온 + 5년 이동평균 그래프
# ---------------------------------------------------------------------------
fig_line = go.Figure()

fig_line.add_trace(
    go.Scatter(
        x=yearly["연도"],
        y=yearly["평균기온"],
        mode="lines+markers",
        name="연도별 평균기온",
        line=dict(color="blue", width=2),
        marker=dict(size=6),
    )
)

fig_line.add_trace(
    go.Scatter(
        x=yearly["연도"],
        y=yearly["5년 이동평균"],
        mode="lines",
        name="5년 이동평균",
        line=dict(color="orange", width=3, dash="dash"),
    )
)

fig_line.add_vrect(
    x0=start_year,
    x1=end_year,
    fillcolor="lightgreen",
    opacity=0.15,
    layer="below",
    line_width=0,
)

fig_line.update_layout(
    title="서울 연도별 평균기온 및 5년 이동평균",
    xaxis_title="연도",
    yaxis_title="기온 (℃)",
    hovermode="x unified",
    template="seaborn",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)

st.plotly_chart(fig_line, use_container_width=True)

# ---------------------------------------------------------------------------
# 9. 연도별 평균 일교차 그래프
# ---------------------------------------------------------------------------
fig_range = go.Figure()

fig_range.add_trace(
    go.Scatter(
        x=yearly["연도"],
        y=yearly["평균일교차"],
        mode="lines+markers",
        name="연도별 평균 일교차",
        line=dict(color="red", width=2),
        marker=dict(size=6),
    )
)

fig_range.add_vrect(
    x0=start_year,
    x1=end_year,
    fillcolor="lightgreen",
    opacity=0.15,
    layer="below",
    line_width=0,
)

fig_range.update_layout(
    title="서울 연도별 평균 일교차",
    xaxis_title="연도",
    yaxis_title="일교차 (℃)",
    hovermode="x unified",
    template="seaborn",
)

st.plotly_chart(fig_range, use_container_width=True)

# ---------------------------------------------------------------------------
# 10. 원본 데이터 미리보기
# ---------------------------------------------------------------------------
with st.expander("원자료 미리보기"):
    st.dataframe(df.head(20), use_container_width=True)
