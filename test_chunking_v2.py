# -*- coding: utf-8 -*-
"""문서청킹 파이프라인 가드 테스트 (P2-23, 2026-08-17).

엔진 회귀(test_engine/test_registry/test_cases)와 별개 트랙 — 청킹 실행 전
`python -m pytest test_chunking_v2.py -q`로 가드가 살아있는지 확인한다.
배경: 10-4절 xlrd 유실 사건(의존성 부재 → .xls 조용히 0청크 → 2,345청크 증발).
"""
import json
import os

import pytest

from chunking_lib_v2 import (
    PIPELINE_DEPENDENCIES,
    GROUPED_DOC_TYPES,
    ChunkWriter,
    GroupEmitter,
    assert_pipeline_dependencies,
    chunk_count_regression_guard,
)


def test_dependencies_all_present_in_current_env():
    # 현재 환경에 필수 파서 6종이 전부 있어야 한다 — 하나라도 없으면
    # 다음 청킹 실행이 조용히 열화되므로, 이 테스트 실패 = 즉시 pip install 신호.
    assert assert_pipeline_dependencies() is True


def test_dependencies_missing_package_raises():
    with pytest.raises(RuntimeError) as ei:
        assert_pipeline_dependencies(deps=PIPELINE_DEPENDENCIES + ("존재하지_않는_패키지_xyz",))
    assert "존재하지_않는_패키지_xyz" in str(ei.value)


def _write_lines(path, n):
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write('{"chunk_id": "c%d"}\n' % i)


def test_count_guard_blocks_shrink(tmp_path):
    idx = str(tmp_path / "index.jsonl")
    _write_lines(idx, 10)
    with pytest.raises(RuntimeError) as ei:
        chunk_count_regression_guard(7, idx, allow_shrink=False)
    assert "10" in str(ei.value) and "7" in str(ei.value)


def test_count_guard_passes_equal_or_growth(tmp_path):
    idx = str(tmp_path / "index.jsonl")
    _write_lines(idx, 10)
    assert chunk_count_regression_guard(10, idx, allow_shrink=False) is True
    assert chunk_count_regression_guard(15, idx, allow_shrink=False) is True


def test_count_guard_explicit_shrink_override(tmp_path):
    idx = str(tmp_path / "index.jsonl")
    _write_lines(idx, 10)
    assert chunk_count_regression_guard(7, idx, allow_shrink=True) is True


def test_count_guard_first_run_no_baseline(tmp_path):
    assert chunk_count_regression_guard(5, str(tmp_path / "없는파일.jsonl")) is True


def test_count_guard_env_var_override(tmp_path, monkeypatch):
    idx = str(tmp_path / "index.jsonl")
    _write_lines(idx, 10)
    monkeypatch.setenv("CHUNK_ALLOW_SHRINK", "1")
    assert chunk_count_regression_guard(7, idx) is True
    monkeypatch.delenv("CHUNK_ALLOW_SHRINK")
    with pytest.raises(RuntimeError):
        chunk_count_regression_guard(7, idx)


# ── P2-13 그룹청킹 L1/L2 (2026-08-17) ──────────────────────────────

def _emit(rows):
    """rows: [(row_id, text, is_header)] → (전체 청크, 그룹들, 행들)"""
    w = ChunkWriter()
    ge = GroupEmitter(w, "테스트", "공사비내역서", r"E:\FarmingDesign\가상.pdf")
    for rid, text, is_hdr in rows:
        if is_hdr:
            ge.header_row(rid, text)
        else:
            ge.row(rid, text, "table_extract")
    ge.flush()
    groups = [c for c in w.chunks if c.get("chunk_level") == "group"]
    l2 = [c for c in w.chunks if c.get("chunk_level") == "row"]
    return w.chunks, groups, l2


def test_group_emitter_header_opens_group_and_rows_reference_it():
    chunks, groups, l2 = _emit([
        ("p1-t1-r1", "0102. 기초공사", True),
        ("p1-t1-r2", "버림콘크리트 | 25-21-120 | 10 | ㎥ | 99,000 | 990,000", False),
        ("p1-t1-r3", "잡석다짐 | 100mm | 50 | ㎡ | 5,000 | 250,000", False),
    ])
    assert len(groups) == 1 and len(l2) == 2
    g = groups[0]
    assert g["doc_subtype"] == "그룹"
    assert g["extraction_quality"] == "group_rollup"
    assert g["group_member_rows"] == ["p1-t1-r2", "p1-t1-r3"]
    assert all(r["parent_group_id"] == g["chunk_id"] for r in l2)
    # L2 행은 설계상 무태깅(주제축 태깅은 그룹에서만)
    assert all(r["topic_tags"] == [] for r in l2)
    # 그룹은 헤더+행 합본으로 태깅 — '기초공사/콘크리트'가 토목 키워드에 걸림
    assert "토목" in g["topic_tags"]


def test_group_emitter_tags_from_member_rows_not_only_header():
    # 헤더가 무의미해도(태그 안 걸림) 부품 행의 '철골'이 그룹 태깅에 잡혀야 한다
    # — 이게 행 단위 미분류를 그룹이 흡수하는 핵심 개선.
    chunks, groups, l2 = _emit([
        ("s-r1", "3. 공사", True),
        ("s-r2", "철골 트러스 상현재 | 각형강관 125*75", False),
    ])
    assert "시설" in groups[0]["topic_tags"]


def test_group_emitter_headerless_run_is_single_code_list_group():
    chunks, groups, l2 = _emit([
        ("s-r1", "SC-101 | 685,000", False),
        ("s-r2", "SC-102 | 986,400", False),
    ])
    assert len(groups) == 1
    assert groups[0]["doc_subtype"] == "그룹(코드나열)"
    assert groups[0]["section_context"] is None
    assert len(l2) == 2


def test_group_emitter_multiple_groups_and_empty_flush_safe():
    chunks, groups, l2 = _emit([
        ("r1", "1-1. 기초공사", True),
        ("r2", "터파기 | 100 | ㎥", False),
        ("r3", "1-2. 골조공사", True),
        ("r4", "기둥 | 각형강관", False),
        ("r5", "서까래 | 파이프", False),
    ])
    assert len(groups) == 2 and len(l2) == 3
    assert groups[0]["group_member_rows"] == ["r2"]
    assert groups[1]["group_member_rows"] == ["r4", "r5"]
    # 빈 emitter flush는 무해
    w = ChunkWriter()
    GroupEmitter(w, "t", "공사비내역서", "x.pdf").flush()
    assert w.chunks == []


def test_grouped_doc_types_scope_is_three_tabular_types():
    # 방법론 4-2절: 공정표·기자재현황은 v1 단위 유지 — 스코프 드리프트 가드
    assert GROUPED_DOC_TYPES == {"공사비내역서", "설계예산서", "수량산출서"}


# ── P2-16 skip 재처리: 수동 doc_type 지정 + 손상 .xls 관대 판독 (2026-08-17) ──

def test_manual_override_files_all_exist():
    # 오버라이드 대상이 이름변경/삭제되면 지정이 조용히 무효화되므로 실존을 가드
    import build_document_chunks_full_v2 as full
    from chunking_lib_v2 import ROOT
    for rel in list(full.DOC_TYPE_OVERRIDES) + list(full.SKIP_OVERRIDES):
        assert os.path.exists(os.path.join(ROOT, rel)), rel


def test_classify_applies_doc_type_override():
    import build_document_chunks_full_v2 as full
    from chunking_lib_v2 import ROOT
    case, dt = full.classify(os.path.join(
        ROOT, "스마트팜스펙/견적참조/논산딸기조윤정님75각 외몽골셀액분리(최종).pdf"))
    assert dt == "공사비내역서" and case == "조윤정"
    case, dt = full.classify(os.path.join(
        ROOT, "스마트팜스펙/견적참조/2025년 무화과(이명환)-각125.xls"))
    assert dt == "공사비내역서"  # 종전 "미분류" — P2-16 수동 지정


def test_xls_lenient_loader_reads_damaged_file_and_restores_xlrd():
    # 수현건설 견적서: strict xlrd는 SUPBOOK utf-16 손상으로 실패하던 파일
    import xlrd.biffh
    from chunking_lib_v2 import ROOT, _xls_sheets_lenient
    strict_before = xlrd.biffh.unicode
    sheets = _xls_sheets_lenient(os.path.join(ROOT, "스마트팜스펙/견적참조/수현건설임미라님견적서.xls"))
    assert sheets is not None
    assert sum(len(rows) for rows in sheets.values()) > 100
    # 패치는 함수 내부에서만 적용되고 원상복구돼야 한다(정상 파일 strict 경로 보존)
    assert xlrd.biffh.unicode is strict_before


def test_xls_lenient_loader_none_for_nonexistent():
    from chunking_lib_v2 import _xls_sheets_lenient
    assert _xls_sheets_lenient(r"E:\FarmingDesign\없는파일_zzz.xls") is None


# ── P2-14 매니페스트(4상태 diff) · 오버레이 (2026-08-17) ──────────────────

def test_file_fingerprint_and_manifest_roundtrip(tmp_path):
    from chunking_lib_v2 import file_fingerprint, load_manifest, save_manifest
    f = tmp_path / "a.txt"
    f.write_text("스마트팜", encoding="utf-8")
    fp = file_fingerprint(str(f))
    assert len(fp["sha256"]) == 64 and fp["size"] == len("스마트팜".encode("utf-8"))
    # 내용이 같으면 지문 동일(결정론)
    assert fp["sha256"] == file_fingerprint(str(f))["sha256"]
    # 매니페스트: 없으면 스켈레톤, 저장/재로드 왕복 보존
    mpath = str(tmp_path / "manifest.json")
    m = load_manifest(mpath)
    assert m["files"] == {} and m["last_run"] is None
    m["files"]["x.pdf"] = {"sha256": fp["sha256"], "status": "processed"}
    m["last_run"] = "T01"
    save_manifest(m, mpath)
    assert load_manifest(mpath) == m


def test_classify_file_states_four_buckets():
    from chunking_lib_v2 import classify_file_states
    mf = {
        "무변경.pdf": {"sha256": "AAA", "status": "processed"},
        "변경.pdf": {"sha256": "OLD", "status": "processed"},
        "삭제.pdf": {"sha256": "GONE", "status": "processed"},
        "이미묘비.pdf": {"sha256": "T", "status": "tombstoned"},
    }
    current = {
        "무변경.pdf": {"sha256": "AAA", "mtime": 1, "size": 1},
        "변경.pdf": {"sha256": "NEW", "mtime": 2, "size": 2},
        "신규.pdf": {"sha256": "FRESH", "mtime": 3, "size": 3},
    }
    s = classify_file_states(current, mf)
    assert s["unchanged"] == ["무변경.pdf"]
    assert s["changed"] == ["변경.pdf"]
    assert s["new"] == ["신규.pdf"]
    assert s["deleted"] == ["삭제.pdf"]  # 이미 tombstoned인 항목은 재보고 안 함


def test_apply_overlay_overrides_marks_and_disambiguates():
    from chunking_lib_v2 import apply_overlay
    chunks = [
        {"chunk_id": "c1", "source_file": "a.pdf", "topic_tags": [], "doc_type": "공사비내역서"},
        {"chunk_id": "c1", "source_file": "b.pdf", "topic_tags": [], "doc_type": "공사비내역서"},
        {"chunk_id": "c2", "source_file": "a.pdf", "topic_tags": ["시설"], "doc_type": "시방서"},
    ]
    overlay = [
        # source_file로 한정 — a.pdf의 c1만 보정돼야 한다(chunk_id는 파일 간 충돌 가능)
        {"chunk_id": "c1", "source_file": "a.pdf", "fields": {"topic_tags": ["장비"], "chunk_id": "해킹시도"}},
        {"chunk_id": "없는id", "fields": {"topic_tags": ["부지"]}},
    ]
    view, n_applied, n_unmatched = apply_overlay(chunks, overlay)
    assert n_applied == 1 and n_unmatched == 1
    a1 = next(c for c in view if c["source_file"] == "a.pdf" and c["chunk_id"] == "c1")
    b1 = next(c for c in view if c["source_file"] == "b.pdf" and c["chunk_id"] == "c1")
    assert a1["topic_tags"] == ["장비"] and a1["manual_overlay"] is True
    assert a1["chunk_id"] == "c1"          # 식별자 필드는 오버라이드 불가
    assert b1["topic_tags"] == [] and "manual_overlay" not in b1
    # 원본 리스트 불변(뷰만 갱신)
    assert chunks[0]["topic_tags"] == []


# ── P3-21 HWP 직접 추출 (2026-08-17) ─────────────────────────────────

def test_hwp_extract_reads_real_spec_document():
    # 07-23 "hwp 스캔본" 판정이 오진이었음을 고정하는 회귀: 김해농원 시방서는
    # 텍스트 문서이고 BodyText에서 4만 자 이상이 추출돼야 한다.
    from chunking_lib_v2 import ROOT, hwp_extract_text
    p = os.path.join(ROOT, "스마트팜스펙", "시방서(RFQ), 견적서(세부내역서QOM), 도면(설계도서)",
                     "기후변화 대응 경주형 연동하우스 보급 시범사업 온실공사 김해농원", "시방서.hwp")
    r = hwp_extract_text(p)
    assert not r["encrypted"]
    assert len(r["text"]) > 30000
    assert "시방서" in r["text"] and "철 골 공 사" in r["text"]  # 실제 조항 어휘
    # 규격 표기 그리스 문자(Φ 등)는 노이즈 필터가 지우면 안 된다
    from chunking_lib_v2 import _HWP_NOISE
    assert _HWP_NOISE.sub("", "Φ31.8×1.7t") == "Φ31.8×1.7t"


def test_chunk_hwp_produces_paragraph_chunks_with_section_context():
    from chunking_lib_v2 import ROOT, ChunkWriter, chunk_hwp
    w = ChunkWriter()
    p = os.path.join(ROOT, "스마트팜스펙", "시방서(RFQ), 견적서(세부내역서QOM), 도면(설계도서)",
                     "기후변화 대응 경주형 연동하우스 보급 시범사업 온실공사 김해농원", "시방서.hwp")
    n = chunk_hwp(w, p, "김해농원", "시방서", None)
    assert n > 100                                   # 문단 다수
    assert all(c["extraction_quality"] == "hwp_text" for c in w.chunks)
    assert any(c["section_context"] for c in w.chunks)  # 헤더 캐리포워드 동작
    assert not w.skipped_files


def test_load_overlay_missing_empty_and_corrupt(tmp_path):
    from chunking_lib_v2 import load_overlay
    assert load_overlay(str(tmp_path / "없음.jsonl")) == []
    ok = tmp_path / "ok.jsonl"
    ok.write_text('{"chunk_id": "c1", "fields": {"topic_tags": ["부지"]}}\n\n', encoding="utf-8")
    assert len(load_overlay(str(ok))) == 1
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{깨진 json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_overlay(str(bad))  # 손보정 파일 파손은 조용히 무시하지 않고 중단


# ── P2-15 Layer B 8도메인 병렬 태깅 + --retag-only (2026-08-17) ───────────

def test_tag_domains_b_hits_expected_domains():
    from chunking_lib_v2 import tag_domains_b
    assert "전기" in tag_domains_b("분전반 설치 및 배선 공사, 누전차단기 포함")
    assert "통신" in tag_domains_b("RS-485 게이트웨이로 원격 모니터링")  # RS-?485 정규식
    assert "구동" in tag_domains_b("보온커튼 개폐모터(감속기 1HP)")
    assert "장애대응" in tag_domains_b("하자 보증기간 2년, 정기점검 포함")
    assert "데이터활용" in tag_domains_b("생육 데이터 수집·로깅 대시보드")
    assert "시설구축" in tag_domains_b("골조 및 기초 콘크리트, 구조계산 KDS 기준")
    assert tag_domains_b("무관한 문장") == []


def test_domain_b_engine_expect_after_expansion():
    # 방법론 3-2절 원표에선 B4~B8이 전부 None(미모델링)이었고 이 테스트가 그
    # 공백을 가드했다. 2026-08-17 사용자 결정(B4~B8 확장)으로 의도적으로 갱신:
    # None은 더 이상 없어야 하고(전 도메인 검토 완료), 각 도메인의 판정 성격을 고정.
    from chunking_lib_v2 import DOMAIN_B_ENGINE_EXPECT
    assert all(v for v in DOMAIN_B_ENGINE_EXPECT.values())          # None/빈값 없음
    assert "WARRANTY_STATUTORY" in DOMAIN_B_ENGINE_EXPECT["장애대응"]  # 법정 상수 연결
    assert "온실설치 2년" in DOMAIN_B_ENGINE_EXPECT["장애대응"]
    assert "ELECTRICAL_PUMSEM_LUMP" in DOMAIN_B_ENGINE_EXPECT["전기"]
    # 판단성 도메인은 "부적합 판정"이 명시돼야 한다(검토 안 한 것과 구분)
    assert "부적합 판정" in DOMAIN_B_ENGINE_EXPECT["통신"]
    assert "부적합 판정" in DOMAIN_B_ENGINE_EXPECT["데이터활용"]
    assert "PUMSEM_ITEMS" in DOMAIN_B_ENGINE_EXPECT["구동"]


def test_chunkwriter_adds_domain_tags_and_preserves_tag_text():
    from chunking_lib_v2 import ChunkWriter
    w = ChunkWriter()
    rec = w.add("t", "시방서", None, r"E:\FarmingDesign\x.pdf", "p1",
                "분전반 배선 및 보온커튼 개폐모터 설치", section_context="3. 전기공사")
    assert "전기" in rec["domain_tags_B"] and "구동" in rec["domain_tags_B"]
    assert rec["_tag_text"].startswith("3. 전기공사")  # 재태깅용 원문(섹션 포함) 보존


def test_group_rows_suppress_both_tag_layers():
    # L2 행은 Layer A·B 모두 무태깅(태깅은 그룹에서)
    chunks, groups, l2 = _emit([
        ("r1", "1-1. 전기공사", True),
        ("r2", "분전반 | 1식 | 1,554,000", False),
    ])
    assert groups[0]["domain_tags_B"]  # 그룹은 태깅됨(전기)
    assert all(r["domain_tags_B"] == [] for r in l2)


def test_write_outputs_strips_tag_text_from_index(tmp_path):
    from chunking_lib_v2 import ChunkWriter, write_outputs
    w = ChunkWriter()
    w.add("t", "시방서", None, r"E:\FarmingDesign\x.pdf", "p1", "골조 기초 공사")
    jsonl = tmp_path / "idx.jsonl"
    write_outputs(w, str(jsonl), str(tmp_path / "sum.txt"))
    rec = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
    assert "_tag_text" not in rec          # 정본 인덱스는 날씬하게
    assert "_tag_text" in w.chunks[0]      # 파트(메모리)에는 보존


def test_retag_only_recomputes_from_tag_text(tmp_path, monkeypatch):
    import run_chunk_incremental as ri
    monkeypatch.setattr(ri, "PARTS", str(tmp_path))
    part = {
        "relpath": "가상.pdf",
        "chunks": [
            # 구식 태그(잘못된 값)가 _tag_text 기준으로 재계산돼야 한다
            {"doc_type": "시방서", "chunk_level": None, "section_context": None,
             "topic_tags": ["엉터리"], "domain_tags_B": [], "consulting_tags": [],
             "engine_link": None, "content_summary": "요약",
             "_tag_text": "분전반 배선 공사 골조 기초"},
            # L2 행은 재태깅해도 무태깅 유지
            {"doc_type": "공사비내역서", "chunk_level": "row", "section_context": "1-1. 전기공사",
             "topic_tags": [], "domain_tags_B": [], "consulting_tags": [],
             "engine_link": None, "content_summary": "분전반 | 1식",
             "_tag_text": "1-1. 전기공사 분전반 | 1식"},
            # _tag_text 없는 구세대 청크 → 근사 폴백
            {"doc_type": "시방서", "chunk_level": None, "section_context": "2. 통신",
             "topic_tags": [], "domain_tags_B": [], "consulting_tags": [],
             "engine_link": None, "content_summary": "RS-485 게이트웨이"},
        ],
        "skips": [],
    }
    p = tmp_path / "aaaa.part.json"
    p.write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
    ri.retag_only()
    out = json.loads(p.read_text(encoding="utf-8"))
    c0, c1, c2 = out["chunks"]
    assert "전기" in c0["domain_tags_B"] and "시설구축" in c0["domain_tags_B"]
    assert "엉터리" not in c0["topic_tags"]          # 구식 태그가 교체됨
    assert c1["topic_tags"] == [] and c1["domain_tags_B"] == []  # 행 무태깅 유지
    assert "통신" in c2["domain_tags_B"]             # 폴백 재태깅 동작
