# 2026 2회차 예시 대시보드 (학교별 단일 데이터 구조)

solar-chat-edu(Solar Pro 4)에서 활동지 3번 "완성 프롬프트 예시"로 생성한 코드를 기반으로,
실행 시 발견된 오류 2건을 수정하고 송도고·아라고·(ph/ec 없는) 데이터로 실행 검증한 버전입니다.

## 폴더 구조
```
streamlitapp_2026/
├── main.py              # 대시보드 코드 (3탭: 실험 개요 / 환경 변화 / 생육 결과)
├── requirements.txt     # streamlit, pandas, numpy, plotly
└── data/
    ├── 송도고_환경데이터.csv       # time, temperature, humidity, ph, ec
    └── 송도고_생육결과데이터.csv   # 개체번호, 잎 수(장), 지상부 길이(mm), 지하부길이(mm), 생중량(g)
```

## 다른 학교 데이터로 바꾸는 방법
1. `data/` 안의 CSV 2개를 자교 파일로 교체합니다. 파일명에 "환경" / "생육"만 들어 있으면 인식합니다.
2. `main.py` 안의 "송도고"(제목·page_title 2곳)를 학교명으로 바꿉니다.
3. GitHub에 커밋하면 Streamlit Cloud가 자동으로 다시 배포합니다.

## 수정 내역 (Solar 1차 생성본 대비)
- 환경 탭 `agg(온도=("temp placeholder","first"))` 임시 코드 삭제 (KeyError 원인)
- 산점도 `trendline="ols"` → numpy `polyfit` 추세선 (statsmodels 불필요)
- `use_container_width=True` → `width="stretch"` (Streamlit 최신 버전 경고 제거)
- 환경 데이터 없을 때 `st.stop()` → 안내 메시지만 표시 (생육 탭은 계속 보이도록)
- 열 이름 매칭을 대소문자 무시로 변경 (ec/EC, ph/pH 모두 인식)

## 로컬 실행
```
pip install -r requirements.txt
streamlit run main.py
```
