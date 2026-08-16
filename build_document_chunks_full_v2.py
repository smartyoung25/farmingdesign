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
    ROOT, SPEC_DIR, FACILITY_DIR, ChunkWriter,
    chunk_pdf_by_page, chunk_pdf_table_or_lines, chunk_xlsx, chunk_xls_legacy, chunk_docx,
    write_outputs,
)
import pdfplumber

W = ChunkWriter()
log = []

EXCLUDE_DIRS = {"노지견적", "노지시방서", "대산온실"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".hwp", ".doc"}

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
    return "미분류"


NAME_PATTERNS = [
    re.compile(r"^([가-힣]{2,4})\s*[-–]"),          # "최선동 - 정면골조도"
    re.compile(r"^([가-힣]{2,4})님"),                  # "박규현님..."
    re.compile(r"\[([가-힣]{2,4})\]"),                 # "[맹주연]_..."
    re.compile(r"([가-힣]{2,4})\s*대표님"),             # "백가은 대표님"
    re.compile(r"\(([가-힣]{2,4})\)"),                 # "충남 서산(이준희)"
    re.compile(r"^([가-힣]{2,4})\s*견적서"),            # "박규현 견적서"
    re.compile(r"^([가-힣]{2,4})\s*내역서"),            # "박종훈 내역서"
    re.compile(r"([가-힣]{2,4})농가"),                  # "군산이명환농가-..."
    re.compile(r"([가-힣]{2,4})님"),                    # "이명환 님" 등 중간 등장
]


def guess_case_from_filename(basename):
    for pat in NAME_PATTERNS:
        m = pat.search(basename)
        if m:
            return m.group(1)
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
    else:
        case = "미상"

    doc_type = guess_doc_type(basename, rel_dir)
    return case, doc_type


PAGE_LEVEL_TYPES = {"설계도면", "구조계산서", "시방서", "사업공모"}
TABLE_LEVEL_TYPES = {"공사비내역서", "설계예산서", "수량산출서", "공사공정표",
                     "기자재현황/품셈/가이드라인"}


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
                        W.skip(path, "스캔본이고 OCR본 없음 — 건너뜀(추정 금지)")
                        log.append(f"[{case}] {doc_type} {os.path.basename(path)}: 스캔본, OCR본 없음 → 건너뜀")
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
    for base in (SPEC_DIR, FACILITY_DIR):
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
            reason = {"." + "hwp": "HWP 텍스트 추출 도구 없음(2026-07-23 확인)",
                      ".doc": "구버전 워드(.doc) — python-docx로 못 읽음"}.get(
                ext, "이미지 파일(OCR 미적용)")
            if ext == ".hwp":
                reason = "HWP 텍스트 추출 도구 없음(2026-07-23 확인)"
            W.skip(path, reason)
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
    run()
    write_outputs(
        W,
        os.path.join(ROOT, "문서청킹_인덱스_전체_9축.jsonl"),
        os.path.join(ROOT, "문서청킹_전체_요약_9축.txt"),
        extra_log=log,
    )
