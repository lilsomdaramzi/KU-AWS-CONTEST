# Kiro 작업 가이드

지금 상태: FastAPI + SQLite + 정적 프론트가 **실제로 연결되어 동작**함 (README.md 참고).
Kiro에게는 아래 프롬프트를 그대로 주면 된다.

> 이 저장소는 대학생 이탈 위험 상담 웹서비스다. README.md와 app/, static/ 구조를 유지하면서 다음을 해줘.
> 1. 로그인과 역할(counselor, admin) 추가. 지금은 URL `#admin`으로 관리자 화면을 여는데, 역할 기반으로 바꿔줘. 시스템 구조 탭은 admin만.
> 2. `POST /api/students/{id}/reveal` 호출자와 시각을 access_logs에 사용자 ID까지 남기고, admin 화면에 열람 기록 표를 추가해줘.
> 3. `bedrock_brief()` 를 완성해서 BEDROCK_MODEL_ID가 있으면 Bedrock(Claude)으로 브리핑을 만들고, 실패하면 규칙 브리핑으로 되돌아가게 해줘. 민감 변수(rules.SENS)는 프롬프트에 넣지 마.
> 4. models/*.cbm 이 있으면 `/api/predict` 로 신규 학생 입력 폼(관리자용)을 만들어 실시간 예측 + SHAP 막대를 보여줘.
> 5. SQLite를 유지하되 EB 재배포 때 상담 기록이 지워지지 않도록 RDS(PostgreSQL) 전환 옵션을 환경변수로 추가해줘.
> 6. pytest로 API 테스트 작성.

규칙:
- 실제 라벨(실제, 정탐·오탐)은 서비스 DB에 절대 넣지 않는다
- SHAP은 인과가 아님: 화면·프롬프트 모두 "원인" 대신 "관련 요인"
- 상담 가이드북 문장은 요약만, 원문 인용 금지
