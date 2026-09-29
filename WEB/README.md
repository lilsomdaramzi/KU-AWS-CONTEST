# 학업지속 상담 서비스 (고려대 세종 x AWS AI Innovators Challenge)

이탈 예측 모델(CatBoost + SHAP) 결과를 상담 현장에 연결하는 웹서비스.
화면(HTML/JS) → FastAPI → SQLite → 예측 결과·모델, 구조로 동작한다.

## 구조
```
app/main.py      FastAPI (API + 화면 서빙)
app/rules.py     등급·요인 태깅·지원 매칭·상담 가이드·AI 브리핑 규칙
build_data.py    원천 xlsx/csv/png → data/data.json
load_db.py       data.json → data/app.db (SQLite), static/img
static/          index.html, app.js, style.css, img/
models/          (선택) 조기.cbm, 중도.cbm 을 넣으면 /api/predict 실시간 예측 활성화
```

## 운영 방식: 학기 배치
실시간 예측이 아니라 **학기마다 한 번** 갱신한다. 성적이 확정되는 학기 말이 기준.
1. 성적 확정 → CatBoost로 전체 재학생 예측 + SHAP (노트북)
2. `build_data.py` → `load_db.py` 로 DB 적재
3. 위험 학생 브리핑 일괄 생성 → `data/claude_briefs.json` → briefs 테이블
   - 예선: 우선 상담 대상 20명은 Claude가 사전 작성, 나머지는 예측 결과 기반 자동 초안
   - 본선: 같은 단계를 Bedrock 배치 호출로 자동화 (`app/main.py bedrock_brief`)
4. 학기 중에는 상담 기록만 계속 쌓임

## 로컬 실행
```
pip install -r requirements.txt
uvicorn app.main:app --port 8000        # http://localhost:8000
```
DB를 다시 만들 때만 (레포 루트에서): `python WEB/build_data.py DATA WEB/data && cd WEB && python load_db.py`

관리자 화면(시스템 구조 탭, 연동 정보 표시): 주소 끝에 `#admin`

## 배포: Render
레포 루트의 `render.yaml` 을 Render Blueprint로 연결하면 이 폴더를 기준으로 빌드·실행된다.
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 확인: `/api/health` 가 `{"api":"ok","db":true,...}` 를 반환하면 정상

## 본선 확장 (선택)
- 모델 실시간 연동: 노트북에서 `model_early.save_model('models/조기.cbm')`, `model_mid.save_model('models/중도.cbm')` 저장 → requirements.txt 의 catboost, pandas 주석 해제 후 재배포 → `POST /api/predict` 활성화
- Bedrock 브리핑: 환경변수 `BEDROCK_MODEL_ID` 와 AWS 자격 증명(`bedrock:InvokeModel` 권한)을 설정. 설정 안 하면 규칙 기반 브리핑으로 동작
