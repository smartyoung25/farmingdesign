# 스마트팜 구축 컨설팅 에이전트

입지·설계·운영·경제성 4축 컨설팅 엔진 + 정적 보고서(build_site) + FastAPI 콘솔. 단일 착수점은 작업지시서.md.

## 절대 규칙 (1절 불변 원칙)
- 엔진(smartfarm_engine.py)이 유일한 계산 출처다. 병렬 계산기 금지(엑셀 수식·JS·앱 계층 산술 — 표시 포맷팅만 허용)
- 근거 없는 값 금지. 확보 전까지 [추정]/[확인요망] 표기, 출처(파일명·시트·행/청크)를 병기
- 시세성 값(단가·노임·유가·금리)은 조회하지 않는다 — 인자로 주입만 받는다
- 판단성 값(작목·부지·업체 선정, 최종판정)은 초안·참고까지만. 판정·추천 자동화 금지
- 실측 벤치마크가 회귀 기준이다. 원채원 ROI 14.2%·Payback 7.1년·실질ROI 28.3%가 안 나오면 작업을 멈추고 원인부터 찾는다
- 테스트를 지우거나 skip으로 바꿔 통과시키지 않는다
- ACTUALS·BENCHMARK_BANDS 값 변경은 원문 확보·대조를 거쳐서만

## 사실성
- 열어보지 않은 문서·코드에 대해 추측하지 않는다. 파일을 먼저 읽고 답한다
- 자료에 없는 수치·담당자·일정은 만들지 않고 '확인 필요'로 표시한다
- 자료 간 모순은 본문에 섞지 않고 '이견' 항목으로 분리한다
- 완료 보고는 "완료했습니다" 대신: 확인한 것 / 확인하지 못한 것 / 사용자가 직접 봐야 할 지점

## 명령어
- 착수 전 회귀(필수): python -m pytest test_engine.py test_registry.py test_cases.py -q
- 전체: python -m pytest test_engine.py test_registry.py test_cases.py test_chunking_v2.py test_webapp.py -q
  (기대 passed 수의 원본은 작업지시서 2절 — 여기 복제하지 않음)
- 사이트 생성: python build_site.py — "생성 완료" 출력 라인을 눈으로 확인(stderr 삼키면 조용한 실패, 16차 사고)
- 웹앱: python -m uvicorn webapp:app --port 8600 (.claude/launch.json)
- 커밋 메시지는 파일로 쓰고 git commit -F <파일> (PowerShell 한국어 인용부호 깨짐)

## 환경 특성 (반복 확인됨)
- pip 패키지가 세션 간 유실된다(xlrd 2회, pdfplumber 등). 파서·웹앱 작업 전 test_chunking_v2/test_webapp가
  의존성 가드 역할 — importorskip으로 조용히 skip되므로 skip 수를 확인할 것
- git dubious ownership 시: git config --global --add safe.directory E:/FarmingDesign

## 작업 관례
- 과제 1건 = 차수 1개 = 커밋 1개. 작업지시서 "갱신 이력" 맨 위에 항목 추가(검증한 것/안 한 것 명시) + 헤더 최종 갱신 한 줄 교체
- 3개 이상 파일을 건드리는 변경은 계획을 먼저 제시
- 판단이 갈리면 조용히 고르지 않고 선택지를 제시(프로젝트 관례: 사용자 결정 기록)
- 요청한 범위만 손댄다. 인접 코드를 "개선"하지 않는다

## 손대지 말 것
- 문서청킹_인덱스_*.jsonl 수기 편집 금지 — 재생성은 run_chunk_incremental.py로만. 인덱스는 검색 계층일 뿐
  제2의 계산 출처가 아니다(청크 값의 엔진 승격은 원문 확인 → 레지스트리 등록 → 드리프트 가드 절차로만)
- 노지견적/·노지시방서/·대산온실/ — 스코프 제외(EXCLUDE_DIRS, P3-22 사용자 결정)
- cases/gyeongbuk_ddalgi.json 0바이트 — 설계된 tombstone(삭제·복구 금지)

## 압축
- 압축할 때 항상 보존: 위 절대 규칙 · 회귀 명령 · 이번 세션에서 수정한 파일 전체 목록 · 미커밋 변경 여부 · 확정된 사용자 결정
