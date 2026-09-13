"""
문서청킹 전면 확장 — `스마트팜스펙/` 전체 + `시설평가/` 전체를 자동 분류·청킹·태깅한다.
파일럿(5개 사례, `build_document_chunks.py`)에서 검증된 로직(`chunking_lib.py`)을 그대로 쓰되,
파일이 너무 많아(230여개) 사람이 하나씩 매핑하는 대신 파일명 규칙으로 자동 분류한다.
자동분류는 필연적으로 파일럿의 수동매핑보다 부정확하다 — 부정확한 부분은 숨기지 않고
요약 통계에 그대로 남긴다.

명시적으로 제외하는 것 (근거 없이 채우지 않고 로그에 남김):
  - 스캔 이미지(.png/.jpg) — 이 환경에 OCR 도구 없음(2026-07-23 확인)
  - .hwp — 텍스트 추출 도구 없음(2026-07-23 확인)
  - .doc(구버전 워드) — python-docx가 못 읽음
  - 엑셀 락파일(~$로 시작)
  - `노지견적/`·`노지시방서/`(관수/양액 자재) — 온실 중심 엔진 스코프 밖 후보,
    설계문서 9절에 남긴 미해결 질문이라 이번 확장에서도 스코프 포함 여부 미확정 → 제외
  - `대산온실/` — 카카오톡 스크린샷 이미지만 있고 문서가 없음
  - 완전 중복 파일(MD5 해시 동일) — 실제로 우민재/이두희/한일그린텍 자료가 `견적참조/`에
    파일명만 바꿔 그대로 복제돼 있는 걸 확인함(2026-07-24)

실행: python build_document_chunks_full.py
출력: 문서청킹_인덱스_전체.jsonl, 문서청킹_전체_요약.txt
"""
import glob
import hashlib
import os
import re

from chunking_lib_v2 import (
    ROOT, SPEC_DIR, FACILITY_DIR, RESEARCH_DIR, ChunkWriter,
    chunk_pdf_by_page, chunk_pdf_table_or_lines, chunk_xlsx, chunk_xls_legacy, chunk_docx,
    chunk_hwp, chunk_image_ocr, chunk_pdf_scan_ocr, write_outputs,
)
import pdfplumber

W = ChunkWriter()
log = []

EXCLUDE_DIRS = {"노지견적", "노지시방서", "대산온실"}
# P3-21(2026-08-17): .hwp 제거 — "hwp 스캔본" 판정(07-23)은 오진(8건 전부
# BodyText 텍스트 실존), chunk_hwp()가 직접 추출.
# P3-21b(2026-08-17): 이미지 확장자 제거 — winocr(Windows 내장 OCR, 한국어)로
# chunk_image_ocr()가 처리한다(품질 ocr_noisy 정직 라벨).
SKIP_EXT = {".doc"}

# ── doc_type 분류 규칙 (파일명 기준, 우선순위 순) ──
# "검토서"는 이 말뭉치에서 실제로 열어본 4건(이두희x3, 이준호x1) 전부 구조계산서였다
# (동일 사무소 템플릿 "Doc. No. 25-xxxx 구조계산서" + "구조 안전 확인서") — 별도 유형으로
# 안 두고 구조계산서에 합친다(2026-07-24 확인).
DOC_TYPE_RULES = [
    (re.compile(r"구조\s*계산|구조검토|온실\s*검토서|_검토서|검토서"), "구조계산서"),
    (re.compile(r"수량\s*산출"), "수량산출서"),
    (re.compile(r"공정표"), "공사공정표"),
    (re.compile(r"시방서|공사설명서|설계설명서|특기\s*시방"), "시방서"),
    (re.compile(r"공모계획|과업지시서|과업설명서|안내공고문|입찰공고서|공고문"), "사업공모"),
    (re.compile(r"설계예산서|원가계산서|원가설계도서"), "설계예산서"),
    (re.compile(r"내역서|견적서|산출내역|공내역서"), "공사비내역서"),
    (re.compile(r"도면|배치도|평면도|골조도|단면도|상세도|입면도|시스템도|설계도"), "설계도면"),
]


def guess_doc_type(basename, rel_dir):
    for pat, dtype in DOC_TYPE_RULES:
        if pat.search(basename):
            return dtype
    if rel_dir.startswith("시설평가"):
        return "기자재현황/품셈/가이드라인"
    if rel_dir.startswith("스마트팜연구DB"):
        # 78차: 농진청 국가연구개발보고서. 파일명 규칙이 없어 폴더 기본값을 준다 —
        # 주지 않으면 PDF가 "doc_type 자동분류 실패"로 **전량 스킵**된다(L295).
        return "연구보고서"
    return "미분류"


# ── P2-16(2026-08-17): 파일명 규칙으로 자동분류 실패한 파일의 수동 doc_type 지정 ──
# 원칙: 전 파일 원문을 pdfplumber/pypdf/xlrd로 직접 열어 첫 페이지·행을 확인한
# 근거를 항목별 주석으로 남긴다(근거 없는 지정 금지). 키는 ROOT 기준 relpath(/).
DOC_TYPE_OVERRIDES = {
    # 세종 소재 설계사무소 건축설계집 — 표지 "Architecture PLAN. CONSTRUCTION
    # SUPERVISION..." + 가설건축물 면적 개요 + 도면 구성(마구평리 스마트팜 신축공사)
    "스마트팜스펙/견적참조/0617 스마트팜-마구평리 392-1_All (2).pdf": "설계도면",
    "스마트팜스펙/견적참조/20260622 수정 스마트팜-마구평리 392_All.pdf": "설계도면",
    # ㈜서진비에스 견적서 표지(견적일 2022-04-25, 강정구 농가 8.4×44×10연동 딸기)
    "스마트팜스펙/견적참조/1. 군산 강정구 농가_8.4×44×10연동_와이드_딸기.pdf": "공사비내역서",
    # 이용균님 4연동(9.6×86.5m) 도면 — 좌표격자(Y0~Y5)·치수 나열, 도면 페이지 구성
    "스마트팜스펙/견적참조/125x75x2.3 측고6m,2중스크린,넥피니언_비닐온실 측고6,2중스크린,넥피니언_비닐온실 설.pdf": "설계도면",
    # 이명환(군산 무화과) 견적서한 — "We thank you for your inquiry and take pleasure in quoting"
    "스마트팜스펙/견적참조/25.12.29 군산_ㅁ75하우스견적_무화과량 이명환 님.pdf": "공사비내역서",
    # 그린팜스글로벌 산출내역서 표지(조윤정, 논산 마구평리, 1091py) — 이동혁 산출내역서와 동일 양식
    "스마트팜스펙/견적참조/논산딸기조윤정님75각 외몽골셀액분리(최종).pdf": "공사비내역서",
    # 다온팜 도면 표제란(도면번호·축척·도면명·승인·심사) 1페이지 도면
    "스마트팜스펙/견적참조/최선동 - 양액시스템.pdf": "설계도면",
    "스마트팜스펙/견적참조/한수진 - 양액제어시스템.pdf": "설계도면",
    # 최혁진 신축공사 도면집 OCR본 — "도면 목록표 A-01..." (건축/양액/전기·제어 51p)
    "스마트팜스펙/최혁진님 온실 내역서/스마트팜 신축공사_최혁진_OCR.pdf": "설계도면",
    # 이명환 무화과 견적 xls(각관 125/75 규격별 변형) — 품명·규격·단가·금액 행 구성,
    # 같은 프로젝트의 견적서한 PDF(위 25.12.29)와 세트. 종전엔 doc_type 미분류인 채
    # 행만 청킹돼 그룹청킹(P2-13)을 못 받던 것을 이 지정으로 편입.
    "스마트팜스펙/견적참조/2025년 무화과(이명환)-각125.xls": "공사비내역서",
    "스마트팜스펙/견적참조/2025년 무화과(이명환)-각75.xls": "공사비내역서",
    # P3-21b(2026-08-17): 맹주연 36p 스캔 — winocr p1 OCR로 정체 확인:
    # "설계도 … 9.4m*99m=3연동 … 맹주연 … 2026" → 설계도면(9.4×99m 3연동 온실
    # 설계도서). P2-16 당시 "내용 확인 불가라 지정 보류"였던 것을 OCR 근거로 해소.
    "스마트팜스펙/견적참조/[맹주연]_충청남도 천안시 서북구 직산읍 양당리 82-2(개발지 포함)_최종.pdf": "설계도면",
    # P3-21c(2026-08-17): 카톡 OCR 사후 분류 — 단독 촬영 1건. OCR 판독 근거:
    # "…아래와 같이 견적합니다" + 보일러·배관 품목·금액 나열(2025년 7월, 김제
    # 소재 수신). 발신 업체·농가명은 판독 불가라 케이스는 미상 유지.
    "스마트팜스펙/견적참조/KakaoTalk_20260715_055923547.jpg": "공사비내역서",
}

# P3-21c(2026-08-17): 카톡 연속촬영 2개 묶음 — OCR 내용 판독으로 일괄 분류.
# 근거(상세는 작업지시서 2절 19차 로그):
#   · 055936807 묶음(8장) = 공사비 내역서를 페이지별 촬영 — _03 "내역서 품 집계표
#     9.6m x 86.5m x 4연동 기초 골조(MS 신형 125-75)…", _06 "공사원가계산서
#     스마트팜 시설 설치공사(3321㎡) … 공급가액 506,000,000" (9.6×86.5×4연동
#     = 3,321.6㎡로 상호 일치), 나머지는 재료비·노무비·경비 내역 행.
#   · 060044177 묶음(30장, _20은 MD5 중복) = 설계도면집을 페이지별 촬영 —
#     _22 표지 "2024년 [오이(행잉거터,드리퍼형식)] 9.6m×86.5m×4연동
#     □-125×75×2.3T(C형) 기준", 측면도·정면도·상세도·환경제어 계통도 등.
#   · 두 묶음의 규격·작물·표지 문구가 기존 이용균 도면 PDF("125x75x2.3 측고6m…설.pdf",
#     p1 "2024년 자립형 스마트팜 시설(이용균님) 9.6m x 86.5m x 4연동 [오이(행잉거터,
#     드리퍼형식)]")와 정확히 일치 → 케이스 "이용균"으로 지정.
for _i in range(8):
    _sfx = "" if _i == 0 else f"_{_i:02d}"
    DOC_TYPE_OVERRIDES[f"스마트팜스펙/견적참조/KakaoTalk_20260715_055936807{_sfx}.png"] = "공사비내역서"
for _i in range(30):
    _sfx = "" if _i == 0 else f"_{_i:02d}"
    DOC_TYPE_OVERRIDES[f"스마트팜스펙/견적참조/KakaoTalk_20260715_060044177{_sfx}.png"] = "설계도면"

# 파일명 케이스 추정이 명백히 틀리는 파일의 수동 케이스 지정 — P2-16.
# 조윤정 건은 괄호 패턴이 "(최종)"을 이름으로 오인하나, 원문 표지에 "조 윤 정 님"
# 명기(그린팜스글로벌 산출내역서, 직접 열람 확인). 기존 처리분의 케이스명은
# 손대지 않는다(이름 추정 로직 전반 개선은 별도 과제).
CASE_OVERRIDES = {
    # ── 90차(2026-09-13, 사용자 지시 "c 진행"): 견적참조 개별 농가 분석 중 발견한
    #   case 오분류를 바로잡는다. NAME_PATTERNS가 파일명에서 사람 이름을 집는데
    #   ①괄호·대괄호 안의 **지명**을 이름으로 오인하고("(천안)"→천안, "[천안]"→천안)
    #   ②`([가-힣]{2,4})농가`가 앞 글자를 먹고("군**산이명환**농가"→산이명환)
    #   ③`^([가-힣]{2,4})\s*(견적서|내역서)`가 **문서 종류**를 이름으로 본다
    #     ("시공견적서"→시공, "산출내역서"→산출, "(최종)"→최종, "(추가)"→추가).
    #   검색 계층만의 문제이나 P2-17 워크플로(프로브→원문 대조→승격)가 case 필터에
    #   기대므로 실사용에 영향이 있다 — 특히 **이두희는 CAPEX_MAJOR 표본 12건 중
    #   하나인데 그 설계예산서 2건이 '천안'으로 잡혀 있었다**.
    #   ⚠️ 파일명에 이름이 **명확히 있는 것만** 바로잡는다(추측 금지). 이름이 없는
    #   문서는 잘못된 이름 대신 '견적참조-미상'으로 되돌린다.
    # (a) 잘못된 이름을 집던 것 — 지명·문서종류 오인
    "스마트팜스펙/견적참조/__원가설계도서_이두희(천안) 20251028.pdf": "이두희",
    "스마트팜스펙/견적참조/원가계산서_이두희(천안) 20251028.pdf": "이두희",
    "스마트팜스펙/견적참조/설계도25 - 233 - [천안] 이두희 온실 검토서_251024 final.pdf": "이두희",
    "스마트팜스펙/견적참조/군산이명환농가-(천창랙피니언커튼1중)-753평-견적서.pdf": "이명환",
    "스마트팜스펙/견적참조/군산이명환농가-(커튼1중)-753평견적서.pdf": "이명환",
    "스마트팜스펙/견적참조/군산이명환농가-천장랙피니언-도면.pdf": "이명환",
    "스마트팜스펙/견적참조/논산딸기백가은님75각 시공 견적서(최종).pdf": "백가은",
    # 이름이 없는 문서 — 문서종류를 이름으로 오인하던 것을 미상으로 되돌린다
    "스마트팜스펙/견적참조/시공견적서.pdf": "견적참조-미상",
    "스마트팜스펙/견적참조/산출내역서(본)_250630.pdf": "견적참조-미상",
    "스마트팜스펙/견적참조/산출내역서(추가)_250630.pdf": "견적참조-미상",
    # (b) 미상이었으나 파일명에 이름이 명확한 것 — 패턴이 접두사·공백·비한글 괄호에 막힘
    "스마트팜스펙/견적참조/00-배광한 설계도서260402.pdf": "배광한",
    "스마트팜스펙/견적참조/00-정택근 설계도서260402.pdf": "정택근",
    "스마트팜스펙/견적참조/1. 군산 강정구 농가_8.4×44×10연동_와이드_딸기.pdf": "강정구",
    "스마트팜스펙/견적참조/221206 윤성호 청년스마트팜 내역서.pdf": "윤성호",
    "스마트팜스펙/견적참조/221206 윤성호 청년스마트팜 기본도면.pdf": "윤성호",
    "스마트팜스펙/견적참조/FIRMMIT_우민재 농가토마토재배 시설하우스 내역서.pdf": "우민재",
    "스마트팜스펙/견적참조/우민재 농가 토마토재배 시설하우스 도면.pdf": "우민재",
    "스마트팜스펙/견적참조/견적서_군산 오기수 농가_0803.pdf": "오기수",
    "스마트팜스펙/견적참조/구창회 설계도면_ 최종.pdf": "구창회",
    "스마트팜스펙/견적참조/최선동복합환경견적서.xlsx": "최선동",
    "스마트팜스펙/견적참조/한수진스마트팜딸기하우스견적서.xls": "한수진",
    "스마트팜스펙/견적참조/25.12.29 군산_ㅁ75하우스견적_무화과량 이명환 님.pdf": "이명환",
    "스마트팜스펙/견적참조/이용균(ms-9.6)(설계예산서).pdf": "이용균",
    "스마트팜스펙/견적참조/이용균(신종리467-7,8) 도면.pdf": "이용균",
    # 한일그린텍: 파일명은 '이영준'이나 ACTUALS·CAPEX_MAJOR가 '한일그린텍'을 쓴다 —
    #   엔진 표기와 맞춘다(같은 프로젝트를 두 이름으로 나누지 않기 위함).
    "스마트팜스펙/견적참조/이영준 설계도면(한일그린텍).pdf": "한일그린텍",
    "스마트팜스펙/견적참조/이영준 설계예산서(한일그린텍).pdf": "한일그린텍",
    # 1차 적용 후 남아 있던 같은 유형 3건(90차 재점검에서 발견) —
    #   "수현건설**임미라**님"의 앞 글자를 먹어 '설임미라', 괄호 안 **업체명**을
    #   이름으로 본 '렉창', 문서종류를 집은 '설계'.
    "스마트팜스펙/견적참조/수현건설임미라님견적서.xls": "임미라",
    "스마트팜스펙/견적참조/스마트팜하우스(렉창)5연동견적서_최선동.xls": "최선동",
    "스마트팜스펙/견적참조/설계내역서_이동혁.pdf": "이동혁",
    "스마트팜스펙/견적참조/논산딸기조윤정님75각 외몽골셀액분리(최종).pdf": "조윤정",
    # P3-21c: 이용균 프로젝트 묶음 — 도면 PDF p1에 "(이용균님)" 명기(P2-16 검사
    # 확인), 카톡 두 묶음은 규격·작물·표지 문구 일치로 동일 프로젝트 판정(위 근거)
    "스마트팜스펙/견적참조/125x75x2.3 측고6m,2중스크린,넥피니언_비닐온실 측고6,2중스크린,넥피니언_비닐온실 설.pdf": "이용균",
}
for _i in range(8):
    _sfx = "" if _i == 0 else f"_{_i:02d}"
    CASE_OVERRIDES[f"스마트팜스펙/견적참조/KakaoTalk_20260715_055936807{_sfx}.png"] = "이용균"
for _i in range(30):
    _sfx = "" if _i == 0 else f"_{_i:02d}"
    CASE_OVERRIDES[f"스마트팜스펙/견적참조/KakaoTalk_20260715_060044177{_sfx}.png"] = "이용균"

# 처리 자체를 명시적으로 제외하는 파일(사유를 정확히 기록) — P2-16
SKIP_OVERRIDES = {
    # 스캔 원본 — 동일 내용의 _OCR.pdf(위에서 설계도면으로 지정)가 별도 파일로
    # 존재·처리되므로, 스캔본을 sibling OCR로 다시 읽으면 같은 내용이 중복 청킹됨
    "스마트팜스펙/최혁진님 온실 내역서/스마트팜 신축공사_최혁진.pdf":
        "스캔 원본 — 동일 내용의 _OCR.pdf가 별도 처리되므로 중복 방지 위해 제외(P2-16)",
    # (P3-21b) 맹주연 스캔 PDF는 winocr p1 판독으로 정체 확인 → SKIP 해제,
    # DOC_TYPE_OVERRIDES "설계도면"으로 이동(스캔 OCR 폴백 경로로 처리됨)
}

# ── 파일명에서 사람 이름 추출 (2026-09-13 103차 개정 — 90차 이월) ──
#   90차가 오분류 3유형을 발견하고 `CASE_OVERRIDES`로 바로잡되 **패턴 자체는 손대지
#   않았다**("패턴 수정은 전 말뭉치의 분류를 바꿔 회귀 범위가 크다"). 103차에 그
#   회귀 범위를 실제로 측정하고 개정한다.
#
#   ⚠️ **방향을 바꿨다** — 더 많이 맞히려 하지 않는다. 시제품으로 "이름을 더 잘 집는"
#   공격적 패턴을 만들어 보니 새 오탐(`비닐온실`·`기백가은`)이 생기고 기존 정답
#   (`맹주연`)을 잃었다. 파일명 기반 이름 추출은 본질적으로 휴리스틱이라 재현율을
#   올리면 정밀도가 깨진다. **틀린 이름은 조용히 틀리지만 '미상'은 복구 가능**하므로
#   **정밀도 우선**으로 보수화했다.
#
#   개정 2가지뿐이다.
#     ① `{2,4}` → `{2,3}`: 앞 글자를 먹던 greedy 결함을 없앤다.
#        "군**산이명환**농가" → 이명환 · "논산딸기**백가은**님" → 백가은 ·
#        "수현건**설임미라**님" → 임미라. 근거: 이 말뭉치의 확인된 이름 22명이
#        **전원 3글자**다(CASE_OVERRIDES 정답세트).
#     ② `NOT_A_NAME` 거부: 지명·문서종류·업체명은 이름이 아니다. 매치돼도 버리고
#        다음 패턴으로 넘어간다 → "시공견적서"·"(천안)"·"(최종)"·"(렉창)"이 이제
#        이름 대신 **미상**으로 떨어진다.
#
#   ✅ 전후 분포 대조(90차가 요구한 것): 견적참조 112파일에서 **변경 14건 ·
#      정답 복원 9건 · 정답 상실 0건 · 새 오탐 0건**, 견적참조 밖 부작용 **0건**.
#      🔴 **바뀌는 파일이 전부 `CASE_OVERRIDES`에 이미 들어 있어**(오버라이드 밖 변경
#      **0건**) 기존 148,424청크 인덱스는 **완전 불변**이다 — 재청킹이 필요 없다.
#   📌 오버라이드는 그대로 둔다. 9건은 이제 패턴만으로도 맞지만, 오버라이드가
#      **원문 확인으로 정한 권위**이고 패턴이 다시 틀려도 값이 흔들리지 않게 한다.
NOT_A_NAME = {
    # 지명 — 괄호·대괄호 안에 들어와 이름으로 오인되던 것
    "천안", "군산", "논산", "서산", "충남", "충북", "경기", "전북", "전남", "경북",
    "경남", "강원", "제주", "부여", "예산", "당진", "공주", "서울", "부산", "대구",
    "광주", "대전", "울산", "세종", "김제", "익산",
    # 문서 종류·도면명 — 문두에서 이름으로 오인되던 것
    "시공", "산출", "설계", "최종", "추가", "견적", "내역", "도면", "배치", "상세",
    "정면", "측면", "후면", "평면", "단면", "연결", "부재", "기본", "총괄", "집계",
    "원가", "수량", "공사", "총공사", "참고",
    # 업체·시설 명칭
    "렉창", "수현", "한일", "그린", "팜스", "서진", "백두", "다온", "미래", "팜스코",
    "비닐", "온실", "비닐온실", "스마트팜", "하우스", "자재", "관리", "작업",
}

NAME_PATTERNS = [
    re.compile(r"^([가-힣]{2,3})\s*[-–]"),          # "최선동 - 정면골조도"
    re.compile(r"^([가-힣]{2,3})님"),                  # "박규현님..."
    re.compile(r"\[([가-힣]{2,3})\]"),                 # "[맹주연]_..."
    re.compile(r"([가-힣]{2,3})\s*대표님"),             # "백가은 대표님"
    re.compile(r"\(([가-힣]{2,3})\)"),                 # "충남 서산(이준희)"
    re.compile(r"^([가-힣]{2,3})\s*견적서"),            # "박규현 견적서"
    re.compile(r"^([가-힣]{2,3})\s*내역서"),            # "박종훈 내역서"
    re.compile(r"([가-힣]{2,3})농가"),                  # "군산이명환농가-" → 이명환
    re.compile(r"([가-힣]{2,3})님"),                    # "이명환 님" 등 중간 등장
]


def guess_case_from_filename(basename):
    """파일명에서 사람 이름을 집는다 — **틀린 이름보다 None(미상)이 낫다**(103차).

    한 패턴이 여러 곳에 맞을 수 있으므로 `finditer`로 전부 훑고, `NOT_A_NAME`에
    걸리는 후보는 버린 뒤 다음을 본다. 모두 버려지면 None이다.
    """
    for pat in NAME_PATTERNS:
        for m in pat.finditer(basename):
            name = m.group(1)
            if name in NOT_A_NAME:
                continue          # 지명·문서종류·업체명은 이름이 아니다
            return name
    return None


def classify(path):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    rel_dir = os.path.dirname(rel)
    basename = os.path.basename(path)

    if basename.startswith("~$"):
        return None  # 엑셀 락파일

    parts = rel.split("/")

    if parts[0] == "스마트팜스펙":
        sub = parts[1] if len(parts) > 1 else None
        if sub in EXCLUDE_DIRS:
            return None
        if sub == "우민재":
            case = "우민재"
        elif sub == "이두희":
            case = "이두희"
        elif sub == "이녕연":
            case = "이녕연"
        elif sub == "최혁진님 온실 내역서":
            case = "최혁진"
        elif sub == "한일그린텍":
            case = "한일그린텍"
        elif sub == "견적참조":
            case = guess_case_from_filename(basename) or "견적참조-미상"
        elif sub and sub.startswith("시방서(RFQ)"):
            # 세 번째 경로 조각이 사업명(사례) 폴더
            case = parts[2] if len(parts) > 2 else "RFQ묶음-미상"
        elif sub == "2025년 청년농업인 스마트팜 자립기반 구축지원사업 준호네 자연농장 이준호":
            case = "이준호"
        elif sub in (
            "2025년 청년농업인 스마트팜 자립기반 구축 지원사업(온실시공)",
            "[입찰대행] 2025년 청년농업인 스마트팜 자립기반 구축 지원사업",
        ):
            case = "제도문서-청년농업인표준"
        else:
            case = "제도문서"
    elif parts[0] == "시설평가":
        case = "범용자료"
    elif parts[0] == "스마트팜연구DB":
        # 78차: 농진청 국가연구개발보고서 모음. 특정 농가 사례가 아니므로 케이스가
        # 아니라 성격 라벨을 붙인다("범용자료"와 구분해야 출처 등급 판단이 쉬워진다 —
        # 이쪽은 실험·실측 보고서라 계수 1차 출처 후보다).
        case = "연구자료"
    else:
        case = "미상"

    # P2-16 수동 지정 우선(케이스·문서유형 모두)
    case = CASE_OVERRIDES.get(rel) or case
    doc_type = DOC_TYPE_OVERRIDES.get(rel) or guess_doc_type(basename, rel_dir)
    return case, doc_type


PAGE_LEVEL_TYPES = {"설계도면", "구조계산서", "시방서", "사업공모"}
TABLE_LEVEL_TYPES = {"공사비내역서", "설계예산서", "수량산출서", "공사공정표",
                     "기자재현황/품셈/가이드라인",
                     # 78차: 연구보고서는 본문(줄)과 실측표가 섞여 있다.
                     # chunk_pdf_table_or_lines가 표를 먼저 뜨고 없으면 줄로 떨어지므로
                     # 표 10·11 같은 계수표를 놓치지 않는다.
                     "연구보고서"}


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_scan_only(path, sample_pages=3):
    # pypdf로 앞 몇 페이지 텍스트 유무만 빠르게 확인(도면 PDF에서 pdfplumber는 느림)
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        n = min(sample_pages, len(reader.pages))
        if n == 0:
            return True
        blanks = 0
        for i in range(n):
            try:
                t = reader.pages[i].extract_text() or ""
            except Exception:
                t = ""
            if not t.strip():
                blanks += 1
        return blanks == n
    except Exception:
        return False


def find_ocr_sibling(path):
    d, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    candidates = glob.glob(os.path.join(d, f"{stem}_OCR{ext}"))
    return candidates[0] if candidates else None


def process_file(path, case, doc_type):
    ext = os.path.splitext(path)[1].lower()
    rel = os.path.relpath(path, ROOT).replace("\\", "/")

    if rel in SKIP_OVERRIDES:  # P2-16: 명시적 제외(정확한 사유 기록)
        W.skip(path, SKIP_OVERRIDES[rel])
        return

    try:
        if ext == ".pdf":
            if doc_type in PAGE_LEVEL_TYPES:
                if is_scan_only(path):
                    ocr = find_ocr_sibling(path)
                    if ocr:
                        n, blank = chunk_pdf_by_page(W, ocr, case, doc_type, None,
                                                      quality_note="ocr_noisy")
                        log.append(f"[{case}] {doc_type} {os.path.basename(path)}: 스캔본 → OCR본 사용 ({n}p, blank={blank})")
                    else:
                        # P3-21b: OCR본이 없으면 winocr로 직접 판독(페이지 렌더→OCR)
                        n, blank = chunk_pdf_scan_ocr(W, path, case, doc_type, None)
                        log.append(f"[{case}] {doc_type} {os.path.basename(path)}: 스캔본 winocr 판독 ({n}p, blank={blank})")
                else:
                    n, blank = chunk_pdf_by_page(W, path, case, doc_type, None)
                    log.append(f"[{case}] {doc_type} {os.path.basename(path)}: {n}p, blank={blank}")
            elif doc_type in TABLE_LEVEL_TYPES:
                nt, nl = chunk_pdf_table_or_lines(W, path, case, doc_type, None)
                log.append(f"[{case}] {doc_type} {os.path.basename(path)}: table_pages={nt}, line_pages={nl}")
            else:
                W.skip(path, f"doc_type 자동분류 실패(미분류) — {os.path.basename(path)}")
        elif ext == ".xlsx":
            n = chunk_xlsx(W, path, case, doc_type, None)
            log.append(f"[{case}] {doc_type} {os.path.basename(path)}: rows={n}")
        elif ext == ".xls":
            n = chunk_xls_legacy(W, path, case, doc_type, None)
            log.append(f"[{case}] {doc_type} {os.path.basename(path)}: rows={n}")
        elif ext == ".docx":
            n = chunk_docx(W, path, case, doc_type, None)
            log.append(f"[{case}] {doc_type} {os.path.basename(path)}: chunks={n}")
        elif ext == ".hwp":
            n = chunk_hwp(W, path, case, doc_type, None)
            log.append(f"[{case}] {doc_type} {os.path.basename(path)}: hwp_chunks={n}")
        elif ext in (".png", ".jpg", ".jpeg"):
            # P3-21b: 이미지 winocr 판독 — 파일명 분류가 안 되는 카톡 캡처 등은
            # doc_type 미분류인 채 정직하게 편입(사후 오버라이드/오버레이로 정제)
            n = chunk_image_ocr(W, path, case, doc_type, None)
            log.append(f"[{case}] {doc_type} {os.path.basename(path)}: img_ocr={n}")
        else:
            W.skip(path, f"처리 대상 아닌 확장자({ext})")
    except Exception as e:
        W.skip(path, f"처리 중 예외: {e}")


def run():
    seen_hash = {}
    n_excluded_dir = 0
    n_skip_ext = 0
    n_lockfile = 0
    n_duplicate = 0
    n_processed = 0

    all_files = []
    for base in (SPEC_DIR, FACILITY_DIR, RESEARCH_DIR):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                all_files.append(os.path.join(dirpath, fn))

    for path in sorted(all_files):
        basename = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()

        if basename.startswith("~$"):
            n_lockfile += 1
            W.skip(path, "엑셀 락파일(임시)")
            continue
        if ext in SKIP_EXT:
            n_skip_ext += 1
            # P3-21/21b: .hwp는 chunk_hwp, 이미지는 chunk_image_ocr로 처리(SKIP_EXT 제외)
            W.skip(path, "구버전 워드(.doc) — python-docx로 못 읽음")
            continue

        result = classify(path)
        if result is None:
            n_excluded_dir += 1
            W.skip(path, "스코프 제외 폴더(노지/대산온실) 또는 락파일")
            continue
        case, doc_type = result

        try:
            h = md5_of(path)
        except Exception as e:
            W.skip(path, f"해시 계산 실패: {e}")
            continue
        if h in seen_hash:
            n_duplicate += 1
            first = seen_hash[h]
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            W.add(case, doc_type, "완전중복", path, "-", "",
                  evidence_status="실측", extraction_quality="skipped_duplicate",
                  duplicate_of=first)
            log.append(f"[중복] {rel} == {first} (MD5 동일) → 청크 생략")
            continue
        seen_hash[h] = os.path.relpath(path, ROOT).replace("\\", "/")

        n_processed += 1
        process_file(path, case, doc_type)

    log.insert(0, f"총 파일 {len(all_files)}개 / 스코프제외폴더 {n_excluded_dir} / "
                  f"확장자제외 {n_skip_ext} / 락파일 {n_lockfile} / MD5중복 {n_duplicate} / "
                  f"실제처리시도 {n_processed}")


if __name__ == "__main__":
    from chunking_lib_v2 import assert_pipeline_dependencies, chunk_count_regression_guard
    assert_pipeline_dependencies()  # P2-23: 처리 시작 전 필수 파서 존재 확인
    run()
    _index_path = os.path.join(ROOT, "문서청킹_인덱스_전체_9축.jsonl")
    chunk_count_regression_guard(len(W.chunks), _index_path)  # P2-23: 총량 급감 차단
    write_outputs(
        W,
        _index_path,
        os.path.join(ROOT, "문서청킹_전체_요약_9축.txt"),
        extra_log=log,
    )
