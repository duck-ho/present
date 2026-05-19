# 📰 뉴스 감성 분석기

특정 기업/주식 종목에 대한 뉴스를 여러 소스에서 자동으로 수집하고, **Claude API**로 각 기사의 감성을 분석하여 **Streamlit 대시보드**로 보여주는 도구입니다.

## ✨ 주요 기능

- **다중 뉴스 소스 수집**: Google News (한/영), 네이버 뉴스, NewsAPI(선택)
- **Claude 기반 감성 분석**: 5단계 라벨(매우 긍정 ~ 매우 부정) + -1.0~+1.0 점수 + 근거 설명
- **대시보드 시각화**
  - 종합 감성 점수
  - 5단계 감성 분포 차트
  - 일자별 감성 추이 시계열 차트
  - 주요 키워드 추출 + Claude의 이슈 요약
  - 원본 기사 테이블 (제목/출처/점수/근거/링크)
- **CSV 다운로드** 지원

## 🚀 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

`.env.example`을 `.env`로 복사하고 키를 채워넣습니다.

```bash
cp .env.example .env
```

```env
# 필수
ANTHROPIC_API_KEY=sk-ant-...

# 선택 (없어도 동작)
NEWSAPI_KEY=
```

- **Claude API 키 발급**: https://console.anthropic.com/
- **NewsAPI 키 발급 (선택)**: https://newsapi.org/ (무료 100 requests/day)

### 3. 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속.

## 🗂️ 프로젝트 구조

```
.
├── app.py                       # Streamlit 대시보드
├── requirements.txt
├── .env.example
└── src/
    ├── analyzer.py              # Claude 감성 분석
    ├── aggregator.py            # 점수/차트 데이터 집계
    └── collectors/
        ├── base.py              # Article 데이터 클래스
        ├── google_news.py       # Google News RSS
        ├── naver_news.py        # 네이버 뉴스 (Google News + site filter)
        └── newsapi.py           # NewsAPI.org (키 필요)
```

## 💡 사용 팁

- 한국 종목은 한글명(예: `삼성전자`)으로, 해외 종목은 영문명(예: `NVIDIA`)으로 검색하면 결과가 풍부합니다.
- 한 번 조회 시 소스당 10개, 총 20-30개 기사를 분석하는 것을 권장합니다 (Claude API 비용/속도 균형).
- 시계열 차트는 기사에 발행일 정보가 있을 때 표시됩니다.

## ⚠️ 주의

- 본 도구는 **참고용**이며 투자 조언이 아닙니다.
- 네이버 검색 API 대신 Google News RSS의 site 필터를 사용합니다(키 불필요). 더 정확한 네이버 결과가 필요하면 [네이버 개발자 센터](https://developers.naver.com)에서 키를 발급받아 별도 컬렉터를 구현하세요.
