import os
from datetime import datetime

import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from src.aggregator import (
    build_dataframe,
    daily_timeseries,
    label_distribution,
    overall_score,
    top_keywords,
)
from src.analyzer import SENTIMENT_LABELS, analyze_articles, summarize_themes
from src.collectors import collect_google_news, collect_naver_news, collect_newsapi

load_dotenv()

st.set_page_config(page_title="뉴스 감성 분석기", page_icon="📰", layout="wide")

st.title("📰 뉴스 감성 분석기")
st.caption("특정 기업/종목에 대한 뉴스를 수집하고 Claude로 감성을 분석합니다.")

with st.sidebar:
    st.header("⚙️ 분석 설정")
    target = st.text_input("기업/종목명", placeholder="예: 삼성전자, NVIDIA, Tesla")

    st.subheader("뉴스 소스")
    use_google_ko = st.checkbox("Google News (한국어)", value=True)
    use_google_en = st.checkbox("Google News (영어)", value=True)
    use_naver = st.checkbox("네이버 뉴스 (RSS)", value=True)
    has_newsapi = bool(os.getenv("NEWSAPI_KEY", "").strip())
    use_newsapi = st.checkbox(
        f"NewsAPI {'(영어)' if has_newsapi else '(키 미설정)'}",
        value=has_newsapi,
        disabled=not has_newsapi,
    )

    st.subheader("기사 수")
    per_source = st.slider("소스당 기사 수", min_value=5, max_value=20, value=10, step=1)

    run = st.button("🚀 수집 & 분석", type="primary", use_container_width=True)

if not os.getenv("ANTHROPIC_API_KEY", "").strip():
    st.error("⚠️ `ANTHROPIC_API_KEY`가 설정되지 않았습니다. `.env` 파일에 키를 추가해주세요.")
    st.code("ANTHROPIC_API_KEY=sk-ant-...", language="bash")
    st.stop()


def _collect_all(target: str, per_source: int) -> list:
    bundle: list = []
    if use_google_ko:
        with st.spinner("Google News (한국어) 수집 중..."):
            bundle.extend(collect_google_news(target, limit=per_source, language="ko"))
    if use_google_en:
        with st.spinner("Google News (영어) 수집 중..."):
            bundle.extend(collect_google_news(target, limit=per_source, language="en"))
    if use_naver:
        with st.spinner("네이버 뉴스 수집 중..."):
            bundle.extend(collect_naver_news(target, limit=per_source))
    if use_newsapi:
        with st.spinner("NewsAPI 수집 중..."):
            bundle.extend(collect_newsapi(target, limit=per_source, language="en"))

    seen_urls = set()
    seen_titles = set()
    deduped = []
    for art in bundle:
        url_key = art.url.split("?")[0]
        title_key = art.title.strip().lower()
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        deduped.append(art)
    return deduped


if run:
    if not target.strip():
        st.warning("기업/종목명을 입력해주세요.")
        st.stop()
    if not any([use_google_ko, use_google_en, use_naver, use_newsapi]):
        st.warning("최소 한 개 이상의 뉴스 소스를 선택해주세요.")
        st.stop()

    articles = _collect_all(target.strip(), per_source)
    if not articles:
        st.warning("수집된 기사가 없습니다. 검색어를 다시 확인해주세요.")
        st.stop()

    st.success(f"✅ {len(articles)}개 기사 수집 완료. 감성 분석을 시작합니다...")

    with st.spinner("Claude로 감성 분석 중..."):
        try:
            sentiments = analyze_articles(target.strip(), articles)
        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {e}")
            st.stop()

    df = build_dataframe(articles, sentiments)
    avg = overall_score(sentiments)

    st.subheader("📊 종합 감성")
    col1, col2, col3 = st.columns(3)
    col1.metric("종합 감성 점수", f"{avg:+.2f}", help="-1.0(매우 부정) ~ +1.0(매우 긍정)")
    col2.metric("분석 기사 수", f"{len(articles)}개")
    pos = sum(1 for s in sentiments if s.score > 0.2)
    neg = sum(1 for s in sentiments if s.score < -0.2)
    col3.metric("긍정/부정 비율", f"{pos} : {neg}")

    st.markdown("---")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("📈 감성 분포")
        dist = label_distribution(sentiments)
        color_map = {
            "매우 긍정": "#1a9850",
            "긍정": "#91cf60",
            "중립": "#bdbdbd",
            "부정": "#fc8d59",
            "매우 부정": "#d73027",
        }
        fig = px.bar(
            dist,
            x="label",
            y="count",
            color="label",
            color_discrete_map=color_map,
            category_orders={"label": SENTIMENT_LABELS},
        )
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="기사 수", height=320)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("🕐 시계열 감성 추이")
        ts = daily_timeseries(df)
        if ts.empty:
            st.info("발행일 정보가 충분하지 않아 시계열 차트를 표시할 수 없습니다.")
        else:
            fig2 = px.line(
                ts,
                x="date",
                y="avg_score",
                markers=True,
                hover_data=["count"],
            )
            fig2.add_hline(y=0, line_dash="dash", line_color="gray")
            fig2.update_layout(
                yaxis_title="평균 감성 점수",
                xaxis_title="",
                yaxis_range=[-1, 1],
                height=320,
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    st.subheader("🔑 주요 키워드 / 이슈 요약")
    kw_col, theme_col = st.columns([1, 2])
    with kw_col:
        kws = top_keywords(sentiments, top_n=12)
        if kws.empty:
            st.info("키워드가 추출되지 않았습니다.")
        else:
            st.dataframe(kws, hide_index=True, use_container_width=True)
    with theme_col:
        with st.spinner("이슈 요약 생성 중..."):
            try:
                themes = summarize_themes(target.strip(), articles, sentiments)
            except Exception as e:
                themes = f"(요약 실패: {e})"
        st.markdown(themes or "_요약 결과가 없습니다._")

    st.markdown("---")

    st.subheader("📰 원본 기사 (감성 분석 결과)")
    display_df = df.copy()
    if "published_at" in display_df.columns:
        display_df["published_at"] = display_df["published_at"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M") if isinstance(x, datetime) else ""
        )
    st.dataframe(
        display_df[["published_at", "label", "score", "title", "source", "reason", "keywords", "url"]],
        column_config={
            "published_at": "발행일시",
            "label": "감성",
            "score": st.column_config.NumberColumn("점수", format="%+.2f"),
            "title": "제목",
            "source": "출처",
            "reason": "근거",
            "keywords": "키워드",
            "url": st.column_config.LinkColumn("링크", display_text="열기"),
        },
        hide_index=True,
        use_container_width=True,
        height=480,
    )

    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 결과 CSV 다운로드",
        data=csv,
        file_name=f"sentiment_{target.strip()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

else:
    st.info("👈 왼쪽 사이드바에서 기업/종목명을 입력하고 **수집 & 분석**을 눌러주세요.")
    with st.expander("ℹ️ 사용 안내"):
        st.markdown(
            """
- **기업/종목명**: 분석하려는 회사/주식 종목을 입력합니다. 예: `삼성전자`, `Apple`, `NVIDIA`
- **뉴스 소스**: Google News(한/영), 네이버 뉴스는 키 없이 동작합니다. NewsAPI는 `NEWSAPI_KEY`가 설정된 경우만 활성화됩니다.
- **감성 분석**: Claude API로 각 기사를 5단계 감성 + -1.0~+1.0 점수 + 근거 텍스트로 평가합니다.
- **결과**: 종합 점수, 감성 분포, 시계열 추이, 키워드/이슈 요약, 원본 기사 표를 제공합니다.
            """
        )
