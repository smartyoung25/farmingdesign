"""
문서청킹 파일럿 — 5개 완전 사례(우민재/이두희/이녕연/최혁진/한일그린텍) 원본자료를
`문서청킹구조_설계공사비시방서.md` 스키마에 따라 추출·청킹·태깅한다.
(2026-07-24 리팩터링: 공통 로직은 `chunking_lib.py`로 이동. 이 파일은 파일별 수동
매니페스트만 유지 — 전체 확장은 `build_document_chunks_full.py` 참고.)

실행: python build_document_chunks.py
출력: 문서청킹_인덱스_파일럿.jsonl (1행 = 1청크)
      문서청킹_파일럿_요약.txt (검증용 통계)
"""
import glob
import os

from chunking_lib import (
    ROOT, SPEC_DIR, ChunkWriter,
    chunk_pdf_by_page, chunk_pdf_table_or_lines, chunk_xlsx, chunk_xls_legacy,
    write_outputs,
)

W = ChunkWriter()
log = []


def g(pattern):
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(pattern)
    return matches[0]


def run():
    # ── 우민재 ──
    case = "우민재"
    base = os.path.join(SPEC_DIR, "우민재")
    p = g(os.path.join(base, "0. 도면*"))
    n, blank = chunk_pdf_by_page(W, p, case, "설계도면", None)
    log.append(f"[{case}] 설계도면 {os.path.basename(p)}: {n}p, blank={blank}")

    p = g(os.path.join(base, "1. 공사내역서*시범사업.xlsx"))
    n = chunk_xlsx(W, p, case, "공사비내역서", "확정본")
    log.append(f"[{case}] 공사비내역서(확정본) {os.path.basename(p)}: rows={n}")

    p = g(os.path.join(base, "*_의견.xlsx"))
    n = chunk_xlsx(W, p, case, "공사비내역서", "의견본")
    log.append(f"[{case}] 공사비내역서(의견본) {os.path.basename(p)}: rows={n}")

    p = g(os.path.join(base, "2. 수량산출*"))
    n = chunk_xlsx(W, p, case, "수량산출서", None)
    log.append(f"[{case}] 수량산출서 {os.path.basename(p)}: rows={n}")

    p = g(os.path.join(base, "3. 공사설명서*"))
    n, blank = chunk_pdf_by_page(W, p, case, "시방서", "설계설명서(공사개요)")
    log.append(f"[{case}] 시방서(설계설명서) {os.path.basename(p)}: {n}p, blank={blank}")

    p = g(os.path.join(base, "4. 공사공정표*"))
    n = chunk_xls_legacy(W, p, case, "공사공정표", None)
    log.append(f"[{case}] 공사공정표 {os.path.basename(p)}: rows={n}")

    p = g(os.path.join(base, "5-1*"))
    n, blank = chunk_pdf_by_page(W, p, case, "시방서", "공사시방서")
    log.append(f"[{case}] 시방서(공사시방서) {os.path.basename(p)}: {n}p, blank={blank}")

    p = g(os.path.join(base, "FIRMMIT*"))
    nt, nl = chunk_pdf_table_or_lines(W, p, case, "공사비내역서", "시공사측 내역서")
    log.append(f"[{case}] 공사비내역서(시공사측) {os.path.basename(p)}: table_pages={nt}, line_pages={nl}")

    p = g(os.path.join(base, "우민재 농가*도면*"))
    n, blank = chunk_pdf_by_page(W, p, case, "설계도면", "시공사측 도면")
    log.append(f"[{case}] 설계도면(시공사측) {os.path.basename(p)}: {n}p, blank={blank}")

    # ── 이두희 ──
    case = "이두희"
    base = os.path.join(SPEC_DIR, "이두희")
    p = g(os.path.join(base, "이두희 천안*"))
    nt, nl = chunk_pdf_table_or_lines(W, p, case, "설계예산서", "원가계산서")
    log.append(f"[{case}] 설계예산서(원가계산서) {os.path.basename(p)}: table_pages={nt}, line_pages={nl}")

    p_primary = g(os.path.join(base, "*_구조계산서.pdf"))
    n, blank = chunk_pdf_by_page(W, p_primary, case, "구조계산서", None)
    log.append(f"[{case}] 구조계산서 {os.path.basename(p_primary)}: {n}p, blank={blank}")

    p_dup = g(os.path.join(base, "*_251024 final.pdf"))
    log.append(f"[{case}] 구조계산서 중복본 {os.path.basename(p_dup)}: 내용 동일 확인됨 → 청크 생성 생략(duplicate_of 표시만)")
    W.add(case, "구조계산서", "중복본", p_dup, "-", "",
          evidence_status="실측", extraction_quality="skipped_duplicate",
          duplicate_of=os.path.relpath(p_primary, ROOT).replace("\\", "/"))

    # ── 이녕연 ──
    case = "이녕연"
    base = os.path.join(SPEC_DIR, "이녕연")
    p_orig = g(os.path.join(base, "이녕연*"))
    ocr_candidates = [f for f in glob.glob(os.path.join(base, "*OCR*"))]
    p_ocr = ocr_candidates[0]
    n, blank = chunk_pdf_by_page(W, p_orig, case, "설계도면", None)
    log.append(f"[{case}] 설계도면(원본, 텍스트 없음/스캔) {os.path.basename(p_orig)}: {n}p, blank={blank} → OCR본으로 대체")
    n, blank = chunk_pdf_by_page(W, p_ocr, case, "설계도면", "OCR추출(품질낮음)",
                                  quality_note="ocr_noisy")
    log.append(f"[{case}] 설계도면(OCR) {os.path.basename(p_ocr)}: {n}p, blank={blank}, 품질=낮음(엔지니어링 도면 OCR)")

    # ── 최혁진 ──
    case = "최혁진"
    base = os.path.join(SPEC_DIR, "최혁진님 온실 내역서")
    p_orig = g(os.path.join(base, "스마트팜 신축공사_최혁진.pdf"))
    n, blank = chunk_pdf_by_page(W, p_orig, case, "설계도면", None)
    log.append(f"[{case}] 설계도면(원본, 스캔) {os.path.basename(p_orig)}: {n}p, blank={blank} → OCR본으로 대체")
    p_ocr = g(os.path.join(base, "스마트팜 신축공사_최혁진_OCR.pdf"))
    n, blank = chunk_pdf_by_page(W, p_ocr, case, "설계도면", "OCR추출(품질낮음)", quality_note="ocr_noisy")
    log.append(f"[{case}] 설계도면(OCR) {os.path.basename(p_ocr)}: {n}p, blank={blank}, 품질=낮음")

    p = g(os.path.join(base, "혁진 스마트팜 온실 신축공사_공사비 내역서.pdf"))
    nt, nl = chunk_pdf_table_or_lines(W, p, case, "공사비내역서", None)
    log.append(f"[{case}] 공사비내역서 {os.path.basename(p)}: table_pages={nt}, line_pages={nl}")
    p_dup = g(os.path.join(base, "혁진 스마트팜 온실 신축공사_공사비 내역서_OCR.pdf"))
    log.append(f"[{case}] 공사비내역서 OCR본 {os.path.basename(p_dup)}: 원본에 이미 텍스트 있음 → 청크 생략(duplicate_of만 표시)")
    W.add(case, "공사비내역서", "OCR본(불필요)", p_dup, "-", "",
          evidence_status="실측", extraction_quality="skipped_duplicate",
          duplicate_of=os.path.relpath(p, ROOT).replace("\\", "/"))

    # ── 한일그린텍 ──
    case = "한일그린텍"
    base = os.path.join(SPEC_DIR, "한일그린텍")
    p = g(os.path.join(base, "설계도면*"))
    n, blank = chunk_pdf_by_page(W, p, case, "설계도면", None)
    log.append(f"[{case}] 설계도면 {os.path.basename(p)}: {n}p, blank={blank}")
    p = g(os.path.join(base, "설계예산서*"))
    nt, nl = chunk_pdf_table_or_lines(W, p, case, "설계예산서", None)
    log.append(f"[{case}] 설계예산서 {os.path.basename(p)}: table_pages={nt}, line_pages={nl}")


run()
write_outputs(
    W,
    os.path.join(ROOT, "문서청킹_인덱스_파일럿.jsonl"),
    os.path.join(ROOT, "문서청킹_파일럿_요약.txt"),
    extra_log=log,
)
