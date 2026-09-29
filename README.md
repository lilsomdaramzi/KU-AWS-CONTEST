# 대학생 이탈 위험 예측 · 학업지속 상담 서비스

고려대학교 세종캠퍼스 x AWS AI Innovators Challenge 예선 제출물입니다.

학생의 입학·성적·학적 정보로 **조기이탈(조기 제적)** 과 **중도이탈(중도 제적)** 을 예측하고,
SHAP으로 학생별 판정 사유를 설명한 뒤, 이를 장학·비교과 지원과 연결하는 **상담 웹서비스**까지 제공합니다.

| 구성 | 내용 |
|---|---|
| 예측 모델 | CatBoost 2종 (조기이탈 / 중도이탈) + SHAP 설명 |
| 지원 데이터 | 교내 장학공지 170건 수집·정제 |
| 웹서비스 | FastAPI + SQLite + HTML/JS, Render 배포 |
| 배포 주소 | https://kus-counsel.onrender.com (헬스체크 [`/api/health`](https://kus-counsel.onrender.com/api/health)) |

## 폴더 구조
```
KU-AWS-CONTEST/
├── README.md
├── requirements.txt          # 모델·크롤링용 패키지
├── render.yaml               # Render Blueprint 배포 설정 (rootDir: WEB)
├── DATA/
│   ├── raw/                  # 입력 데이터 (노이즈 처리된 학생 데이터)
│   ├── output/               # 모델 결과 (성능, 위험군, 예측결과, SHAP, ID별 판정 사유)
│   ├── figures/              # ROC 곡선, SHAP 그림
│   └── 장학공지_crawling.csv  # 정제된 장학공지 170건
├── SCRIPT/
│   ├── 조기_중도이탈모델_Train_Test.ipynb   # 모델 파이프라인 (학습 → 검증 → SHAP)
│   ├── crawl_scholarship.py              # 장학공지 수집
│   └── postprocess_scholarship.py        # 장학공지 정규화·필터링
├── DOCS/
│   ├── 데이터_생성과정.md      # 장학 데이터 정제 과정
│   └── 데이터_명세.md          # 장학 데이터 스키마
└── WEB/                      # 상담 웹서비스 (자세한 내용은 WEB/README.md)
    ├── app/                  # FastAPI (API + 화면 서빙), 규칙 엔진
    ├── static/               # index.html, app.js, style.css, img/
    ├── data/                 # app.db (SQLite), 사전 작성 브리핑
    └── requirements.txt      # 웹서비스용 패키지
```

## 데이터 안내
- `DATA/raw/`의 학생 데이터는 **이미 전처리·가명처리된 버전**입니다. 수치형 변수에 작은 노이즈를 넣었고, 제적 라벨을 추가했습니다 (`_noised_제적라벨`).
- 원본 데이터는 이 저장소에 포함되지 않습니다.
- 웹서비스 DB에는 실제 라벨(실제 이탈 여부, 정탐·오탐)을 넣지 않습니다.

---

## 1. 이탈 예측 모델

- 모델: CatBoost (범주형 변수 직접 처리, 클래스 불균형 보정)
- 두 모델은 **서로 독립**입니다. 한 모델의 예측/라벨을 다른 모델의 입력으로 쓰지 않습니다.
- 학습: `SW_Train_noised_제적라벨.xlsx` (80/20 층화 분할로 Train / Validation)
- 검증: `SW_Test_noised_제적라벨.xlsx` (임계값은 Validation에서 정하고 Test에 그대로 적용)

### DATA/raw
| 파일 | 설명 |
|---|---|
| `SW_Train_noised_제적라벨.xlsx` | 학습 데이터 10,687명 (조기제적 1,382 / 중도제적 506) |
| `SW_Test_noised_제적라벨.xlsx` | 검증 데이터 2,673명 (조기제적 328 / 중도제적 125) |

타겟: `조기_제적여부`, `중도_제적여부` (두 라벨이 동시에 1인 학생은 없음)

### DATA/output
| 파일 | 설명 |
|---|---|
| `모델_성능요약.xlsx` | 두 모델의 Train / Validation / Test 성능 (AUC, PR-AUC, Recall, Precision, Accuracy) |
| `중도이탈_위험군_요약.xlsx` | 중도이탈 위험군 / 저위험군별 인원, 실제 이탈자 수, 이탈 비율 |
| `Test_조기_중도_예측결과.xlsx` | Test 학생별 조기이탈 확률·예측, 중도이탈 확률·위험군 |
| `SHAP_분석결과.xlsx` | 변수 중요도, 변수 방향성, 학생별 주요 요인, 학생 × 변수 SHAP 값 |
| `ID별_판정사유.xlsx` | 학생 ID별 판정 사유 (위험↑ 사유 Top5, 위험↓ 요인 Top3, 설명 문장) |

### DATA/figures
| 파일 | 설명 |
|---|---|
| `roc_early.png`, `roc_mid.png` | 모델별 Train / Validation / Test ROC 곡선 |
| `shap_조기이탈_summary.png`, `shap_중도이탈_summary.png` | 변수별 SHAP 분포 (beeswarm) |
| `shap_조기이탈_dependence.png`, `shap_중도이탈_dependence.png` | 상위 연속형 변수의 값 ↔ SHAP 관계 |
| `shap_ID_<모델>_<ID>.png` | 예시 학생의 waterfall 그림 (판정 과정) |

### 조기이탈 모델
- 대상: 전체 학생 / 타겟: `조기_제적여부`
- 변수 15개: 입학·배경 정보, 1학년 1학기 평점(`평점_1_1`, `평점_1_1_Ponly`), `일반휴학_여부`, `휴학비율`
- 파라미터: `depth=4, learning_rate=0.03, l2_leaf_reg=5, iterations=800`, 클래스 가중치 = 불균형비
- 판정: 확률 ≥ **0.730** → 조기이탈 예측 (Validation에서 Recall ≥ 0.8을 만족하는 가장 높은 임계값)

### 중도이탈 모델
- 대상: 조기제적자를 제외한 학생 / 타겟: `중도_제적여부`
- 변수 33개: 입학·배경 정보 + 누적 성적(전체·직전학기 평점, 성적경고, 성적 변화량·분산, 최저평점, 저성적 학기수) + 학적·활동(휴학, 전과, 다전공, 비교과 등)
- 파라미터: `depth=3, learning_rate=0.03, l2_leaf_reg=10, iterations=400`, 클래스 가중치 = 불균형비의 제곱근
- 판정 (2단계)
  - **위험군**: 확률 ≥ **0.161** (Validation에서 Recall ≥ 0.8을 확보하는 임계값) → 상담·모니터링 대상
  - **저위험군**: 확률 < 0.161
  - 참고: 확률 ≥ 0.388 (F1 최대 임계값)은 위험군 안에서 우선 상담 대상

### 성능

| 모델 | 데이터 | ROC-AUC | Recall | Precision |
|---|---|---|---|---|
| 조기이탈 | Train | 0.965 | 0.807 | 0.755 |
| | Validation | 0.952 | 0.801 | 0.762 |
| | **Test** | **0.947** | **0.799** | **0.746** |
| 중도이탈 (위험군 기준) | Train | 0.918 | 0.864 | 0.200 |
| | Validation | 0.890 | 0.802 | 0.192 |
| | **Test** | **0.905** | **0.816** | **0.196** |

중도이탈 Test 위험군 구성
| 구분 | 학생 수 | 실제 중도이탈 | 이탈 비율 |
|---|---|---|---|
| 위험군 | 521 | 102 | 19.6% (전체 이탈자의 81.6% 포함) |
| └ 우선 상담 (≥0.388) | 169 | 74 | 43.8% |
| 저위험군 | 1,824 | 23 | 1.3% |

### SHAP 해석 요약
- SHAP 값은 로그오즈 단위이며, **양수 = 이탈 위험을 높임, 음수 = 낮춤**입니다.
- **조기이탈**: `휴학비율`(29%), `평점_1_1`(20%), `평균_소득분위`, `일반휴학_여부`, `모집전형` 순으로 영향이 큽니다.
  휴학비율이 높을수록, 1학년 1학기 평점이 낮을수록 위험이 커집니다.
- **중도이탈**: `휴학비율`(20%), `성적변화량_분산`(17%), `비교과_참여횟수`, `휴학학기`, `성적변화량` 순입니다.
  휴학비율이 높을수록, 성적이 떨어질수록 위험이 커지고, 비교과 참여가 많을수록 위험이 낮아집니다.
- 학생별 판정 사유는 `DATA/output/ID별_판정사유.xlsx`에서 확인할 수 있습니다.
  - 표기: `변수=학생값 (전체 기준값) : 확률 A→B (+SHAP)` → 이 요인이 없었다면 확률 A, 실제 예측확률 B

### 실행 방법
```bash
pip install -r requirements.txt
cd SCRIPT
jupyter notebook 조기_중도이탈모델_Train_Test.ipynb   # Run All
```
- 입력은 `DATA/raw/`에서 읽고, 결과는 `DATA/output/`, `DATA/figures/`에 저장됩니다.
- 엑셀 파일은 처음 한 번 읽은 뒤 같은 폴더에 `.pkl` 캐시를 만듭니다 (git에는 올리지 않음).
- 특정 학생 조회 (섹션 8 실행 후): `explain_id(53529)`

### 참고 · 한계
- SHAP은 모델이 **무엇에 기대어 판정했는지**를 보여줄 뿐, 이탈의 **원인**을 증명하지 않습니다. 상담 시 "확인해 볼 신호"로 활용하는 것을 권장합니다.
- `휴학비율`이 두 모델 모두에서 가장 영향력이 큽니다. 이 값이 이탈 이전 시점 기준인지, 이탈까지 누적된 값인지에 따라 해석이 달라질 수 있습니다.
- 1학년 1학기 평점이 "P"(Pass)인 경우 숫자 평점이 결측으로 처리되며, CatBoost는 결측을 가장 낮은 값처럼 다루므로 조기이탈 위험이 높게 계산될 수 있습니다.
- `총재학학기`, `총이수학점`은 이탈 시점까지 누적된 값이라 정답 누수 가능성이 있어 제외했습니다. `현재_학적상태`, `제적_여부`도 타겟 정보이므로 제외했습니다.

---

## 2. 장학공지 데이터

고려대학교 세종캠퍼스 장학공지를 수집·정제해 `DATA/장학공지_crawling.csv`(170건)로 저장했습니다.
열은 `제목`, `성격`, `신청날짜`, `지원대상`, `금액`이며, Excel 호환 UTF-8 BOM CSV입니다.

```bash
pip install -r requirements.txt
python SCRIPT/crawl_scholarship.py          # 1~20페이지 및 상세 글 수집
python SCRIPT/postprocess_scholarship.py    # 기존 CSV에 정규화 규칙만 다시 적용
```

- 출처: [교내장학금 신청 및 선발 안내](https://gpa.korea.ac.kr/koreaSejong/7953/subview.do), [장학공지](https://secu.korea.ac.kr/koreaSejong/7906/subview.do)
- 웹 상세 본문에 없는 첨부파일 전용 정보는 공란일 수 있습니다.
- 실제 신청 전 반드시 원문에서 최신 일정과 자격을 확인하세요.
- 세부 정제 과정과 스키마는 [`DOCS/데이터_생성과정.md`](DOCS/데이터_생성과정.md), [`DOCS/데이터_명세.md`](DOCS/데이터_명세.md)를 참고하세요.

출처 콘텐츠는 라이선스 준수를 위해 그대로 재게시하지 않고 데이터 필드 형태로 요약·재구성했습니다.

---

## 3. 상담 웹서비스 (WEB/)

이탈 예측 결과(CatBoost + SHAP)를 상담 현장에 연결하는 웹서비스입니다. 화면(HTML/JS) → FastAPI → SQLite 구조이며, 화면도 FastAPI가 같이 서빙합니다.

- `WEB/app/main.py`: API + 화면 서빙, `WEB/app/rules.py`: 등급·요인 태깅·지원 매칭·브리핑 규칙
- `WEB/static/`: index.html, app.js, style.css, img/
- `WEB/data/app.db`: 예측 결과·장학·프로그램·상담 기록 DB
- 운영: 학기 배치 예측. 예선은 사전 작성 브리핑 + 규칙 초안, 본선은 Bedrock 연동 예정 (`BEDROCK_MODEL_ID`)

### 로컬 실행
```bash
cd WEB
pip install -r requirements.txt
uvicorn app.main:app --port 8000   # http://localhost:8000
```

### 배포 (Render)
루트 `render.yaml`을 Render Blueprint로 연결하면 `WEB/`을 기준으로 빌드·실행합니다.
- Build: `pip install -r requirements.txt` / Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 헬스체크: `/api/health` → `{"api":"ok","db":true,...}`
- 예선 데모 버전으로 로그인·권한 기능은 아직 없습니다 (본선에서 추가 예정).

자세한 내용은 [`WEB/README.md`](WEB/README.md)를 참고하세요.
