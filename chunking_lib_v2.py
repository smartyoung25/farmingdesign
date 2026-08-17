"""
문서청킹 공통 라이브러리 — `문서청킹구조_설계공사비시방서.md` 스키마의 태깅·청킹 로직.
`build_document_chunks.py`(5개 사례 파일럿)와 `build_document_chunks_full.py`(전체 확장)가
같은 로직을 공유하도록 분리했다(2026-07-24, 파일럿 검증 후 전면 확장하며 리팩터링).

주의: 이 인덱스는 엔진의 계산 출처가 아니다. 엔진 상수 승격은 기존 실측 확인
절차(레지스트리 등록 + 드리프트 가드 테스트)를 그대로 거친다.
"""
import json
import os
import re

import pdfplumber
import openpyxl

ROOT = os.path.dirname(os.path.abspath(__file__))
SPEC_DIR = os.path.join(ROOT, "스마트팜스펙")
FACILITY_DIR = os.path.join(ROOT, "시설평가")


# ── P2-23(2026-08-17): 파이프라인 의존성·산출물 급감 가드 ──────────────
# 배경: 2026-08-16 xlrd 유실 사건(작업지시서 10-4절) — 의존성 부재가 skip 사유로만
# 기록된 채 실행이 계속돼 .xls 파일들이 조용히 0청크가 됐고(기존 대비 2,345청크
# 증발), 병합 후 총량을 이전 실행과 수동 대조하고서야 발견됐다. 2026-08-17엔
# pdfplumber도 같은 방식으로 환경에서 유실돼 있었음이 재확인됨. 조용한 열화를
# 실행 전(의존성 확인)·병합 시(총량 대조) 두 지점의 명시적 중단으로 바꾼다.
PIPELINE_DEPENDENCIES = ("pdfplumber", "pypdf", "openpyxl", "xlrd", "pandas", "docx")


def assert_pipeline_dependencies(deps=PIPELINE_DEPENDENCIES):
    """필수 파서 패키지가 하나라도 없으면 RuntimeError로 즉시 중단한다.
    없는 채 진행하면 해당 포맷 파일 전부가 '읽기 실패' skip으로 조용히 사라진다."""
    import importlib
    missing = []
    for name in deps:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            "청킹 파이프라인 필수 패키지 유실: " + ", ".join(missing)
            + " — pip install 후 재실행할 것 (P2-23 가드: 의존성 없이 진행하면 "
              "해당 포맷이 조용히 0청크가 된다. 10-4절 xlrd 사건 참고)")
    return True


def chunk_count_regression_guard(new_count, index_path, allow_shrink=None):
    """병합 결과 총 청크 수가 기존 인덱스보다 줄면 RuntimeError로 중단한다.
    의도적 축소(파일 삭제·스코프 변경)는 환경변수 CHUNK_ALLOW_SHRINK=1 로만 통과."""
    if allow_shrink is None:
        allow_shrink = os.environ.get("CHUNK_ALLOW_SHRINK") == "1"
    if not os.path.exists(index_path):
        return True  # 첫 실행 — 비교 기준 없음
    with open(index_path, encoding="utf-8") as f:
        old_count = sum(1 for line in f if line.strip())
    if new_count < old_count and not allow_shrink:
        raise RuntimeError(
            f"병합 결과 청크 수 급감: 기존 {old_count} → 신규 {new_count}"
            f"({old_count - new_count} 감소) — 의존성 유실/부분 처리 의심"
            "(10-4절 사건과 동일 패턴). 의도적 축소가 맞으면 "
            "CHUNK_ALLOW_SHRINK=1 환경변수로 재실행할 것")
    return True

# ── 주제축(도메인) 태깅 규칙 ──
# 2026-07-24 개정: 사용자 지정 9개 공학 도메인 축으로 재구성한다.
#   부지 · 토목 · 시설 · 장비 · 전기 · 통신 · 재배환경 · 운영 · 사후관리
# 시방서/설계서/견적서/도면 텍스트(행·페이지)를 이 9개 축으로 분해 태깅한다.
# 한 청크가 복수 축에 걸릴 수 있다(예: "난방기"는 장비이자 재배환경).
# (이전 파일럿의 축: 부지/기후/작물특성/냉난방/광량/CO2/생육관리/운영/유지보수/
#  구조자재/비용공정 — 개정판에서 재배환경·시설·장비 등으로 통합·재배치됨)
TOPIC_KEYWORDS = {
    # 대지·필지·진입·측량 등 '땅' 관련
    "부지": r"부지|필지|대지|지목|용지|진입로|경계|구획|배치도|위치도|측량|녹지|부지경계|지적",
    # 지반·토공·배수·기초토목 등 '토목공사'
    "토목": r"토목|지반|성토|절토|터파기|되메우기|다짐|굴착|잡석|버림\s*콘크리트|기초\s*콘크리트|"
            r"배수|우수|맨홀|측구|집수정|옹벽|포장|부지조성|정지작업|경사|사면|암거|토사|되메움",
    # 온실 구조체·골조·피복 등 '시설(구조물)'
    "시설": r"온실|하우스|골조|철골|트러스|서까래|기둥|중방|들보|파이프|피복|유리|비닐|폴리|외피|"
            r"지붕|천창|측창|측벽|박공|연동|단동|구조물|파형강판|스크린|보온\s*커튼|차광막|개폐부|용마루",
    # 설비·기자재·냉난방장치 등 '장비'
    "장비": r"기자재|장비|설비|양액기|양액|관수|점적|분수|환기팬|유동팬|순환팬|배기팬|난방기|보일러|"
            r"히트\s*펌프|온풍기|냉방기|칠러|제어기|컨트롤러|센서|개폐기|감속기|모터|FCU|팬코일|"
            r"CO2\s*발생|탄산가스\s*발생|약액|배지|양액\s*탱크|히트펌프",
    # 수배전·배선·접지 등 '전기'
    "전기": r"전기|수배전|배전|분전반|배선|접지|차단기|전력|인입|케이블|전등|조명|동력|콘센트|전압|"
            r"한전|누전|간선|전기공사|전기설비|수전|변압기|전기배관",
    # 네트워크·통신 인프라 '통신'
    "통신": r"통신|네트워크|인터넷|유선|무선|LAN|랜|광케이블|광\s*통신|IoT|사물인터넷|원격|공유기|"
            r"라우터|데이터\s*통신|CCTV|IP\s*카메라|통신배관|통신설비",
    # 작물·환경(온습도·광·CO2·양액·냉난방 운용) '재배환경'
    "재배환경": r"재배|작물|작목|토마토|딸기|파프리카|무화과|생육|정식|착과|유인|파종|"
                r"온도|습도|일사|광량|투광|차광|보광|CO2|이산화탄소|양액\s*농도|관비|병해충|방제|"
                r"VPD|보온|냉방|난방|환기|결로|과습|열관류율|열원|생육관리",
    # 운영·인건·에너지비 등 '운영'
    # 농장 '운영' 단계 비용(건설 노무비/재료비는 제외 — 그건 doc_type=견적서/내역서로 포착)
    "운영": r"운영비|운영관리|가동비|가동률|인건비|관리비|전기요금|연료비|에너지비용|난방비|"
            r"유지비|경영|자동화|ICT|복합환경제어",
    # 하자·보수·점검·보증 등 '사후관리'
    "사후관리": r"하자|보수|사후관리|유지관리|점검|보증|보증기간|A\s*/?\s*S|AS\b|내구연한|소모품|"
                r"교체|정기점검|워런티|유지보수",
}
TOPIC_PATTERNS = {k: re.compile(v) for k, v in TOPIC_KEYWORDS.items()}

CAPEX_KEYWORD = re.compile(r"공사비|내역서|재료비|노무비|경비|원가계산")
STRUCT_KEYWORD = re.compile(r"적설|풍속|하중|구조계산|KDS")

# 구조계산서 등 PDF에서 폰트/인증서 메타데이터가 텍스트로 새어나오는 노이즈 패턴
# (2026-07-24 파일럿에서 발견: "Certified by Gen MODEL DATA PROFILE..." 반복)
NOISE_PATTERN = re.compile(r"Certifi|MODEL DATA|GDLicense|Robot\s*Structural|autodesk", re.I)

# 공사비내역서/설계예산서 표에서 "공종 헤더 행"으로 볼 패턴 (예: "1-1. 기초공사", "0102. 기초공사")
SECTION_HEADER_PATTERN = re.compile(r"^\d+([.\-]\d+)*\.?\s*[가-힣]")


def looks_like_noise(text):
    return len(NOISE_PATTERN.findall(text)) >= 2


def is_header_row(cells):
    if not cells or len(cells) > 2:
        return False
    first = cells[0].strip()
    return bool(SECTION_HEADER_PATTERN.match(first))


def tag_topics(text):
    return [name for name, pat in TOPIC_PATTERNS.items() if pat.search(text)]


def engine_link_for(doc_type, text):
    links = []
    if doc_type in ("공사비내역서", "설계예산서", "수량산출서") and CAPEX_KEYWORD.search(text):
        links.append("CAPEX_MAJOR_CATEGORIES")
    if doc_type == "구조계산서" and STRUCT_KEYWORD.search(text):
        links += ["SPEC_TABLE", "REGION_DESIGN_LOAD"]
    return links or None


# ── 컨설팅 단계 태깅 (2026-07-25 추가) ──
# 목적: 각 청크가 스마트팜 시설컨설팅 5단계(진단·설계·비용최적화·운영최적화·유지보수)
# 중 어디에 쓰이는지 표시해, 컨설턴트가 단계별로 근거 청크를 바로 필터링하게 한다.
_C = {
    "진단": re.compile(r"검토|현황|진단|적정성|안전성|적합성|하중|적설|풍하중|구조계산|노후|애로|문제점"),
    "설계": re.compile(r"설계|규격|사양|기준|도면|배치|평면|골조|단면|상세도|시방|KDS|구조검토|용량|제원"),
    "비용최적화": re.compile(r"공사비|내역|단가|금액|수량|재료비|노무비|경비|원가|견적|사업비|보조|자부담|VAT|합계"),
    "운영최적화": re.compile(r"운영|운전|가동|에너지|전기요금|연료비|난방비|인건비|운영비|생산성|수확량|상품률|가동률|자동화|ICT|제어"),
    "유지보수": re.compile(r"하자|보수|사후관리|유지관리|점검|보증|A\s*/?\s*S|내구연한|소모품|교체|정기점검|워런티"),
}
# doc_type만으로도 걸리는 기본 단계(내용 키워드가 약해도 문서 성격상 해당되는 것)
_DOCTYPE_STAGE = {
    "공사비내역서": ["비용최적화", "설계"],
    "설계예산서": ["비용최적화", "설계"],
    "수량산출서": ["비용최적화", "설계"],
    "공사공정표": ["비용최적화"],
    "설계도면": ["설계", "진단"],
    "시방서": ["설계", "진단"],
    "구조계산서": ["진단", "설계"],
    "검토서": ["진단"],
    "기자재현황/품셈/가이드라인": ["비용최적화", "설계"],
}


def consulting_tags(doc_type, text):
    tags = set(_DOCTYPE_STAGE.get(doc_type, []))
    for stage, pat in _C.items():
        if pat.search(text):
            tags.add(stage)
    # 단계 우선순위 순으로 정렬해 결정적 출력
    order = ["진단", "설계", "비용최적화", "운영최적화", "유지보수"]
    return [s for s in order if s in tags]


# ── 성능사양 수치 추출 (견적용) ──
# 수치+단위 토큰을 뽑는다. 단위 뒤에 '원'이 오는 금액은 성능이 아니므로 제외.
SPEC_UNIT = re.compile(
    r"(\d[\d,]*\.?\d*)\s?"
    r"(kcal/?h|kcal|kW/?h|kW|W/㎡·?K|W/m2·?K|W/㎡K|W|kV·?A|kVA|V|A|Hz|"
    r"㎥/?h|m3/?h|㎥/?분|㎥|m3|LPM|L/?min|㎡|m2|mm|cm|Φ|파이|"
    r"℃|°C|kPa|Pa|㎩|%|ppm|μmol|umol|lx|lux|dB|HP|마력|rpm|톤|ton|kg|평)",
    re.I,
)


# ── 비용 수치 추출 (견적/비용최적화용) ──
# 천단위 콤마가 있는 금액/단가 후보. 단, 숫자 바로 뒤에 성능단위가 붙은 값
# (예: 6,000㎥/h, 3,971㎡)은 성능사양이지 금액이 아니므로 제외한다.
MONEY = re.compile(r"\d{1,3}(?:,\d{3})+")


def extract_spec_cost(text):
    specs, spec_starts = [], set()
    for m in SPEC_UNIT.finditer(text):
        spec_starts.add(m.start(1))
        tok = (m.group(1) + m.group(2)).strip()
        if tok not in specs:
            specs.append(tok)
        if len(specs) >= 12:
            break
    costs = []
    for m in MONEY.finditer(text):
        if m.start() in spec_starts:      # 성능수치(6,000㎥ 등)는 금액에서 제외
            continue
        v = m.group(0)
        if v not in costs:
            costs.append(v)
        if len(costs) >= 12:
            break
    return specs, costs


def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()


class ChunkWriter:
    def __init__(self):
        self.chunks = []
        self.skipped_files = []  # (path, reason)

    def add(self, case_name, doc_type, doc_subtype, source_file, page_or_section,
            text, evidence_status="실측", extraction_quality="normal", duplicate_of=None,
            section_context=None):
        text = clean(text)
        noise = looks_like_noise(text)
        tagging_text = text if not noise else ""
        if section_context:
            tagging_text = clean(section_context) + " " + tagging_text
        chunk_id = f"{case_name}_{doc_type}_{doc_subtype or ''}_{page_or_section}".replace(" ", "")
        rec = {
            "chunk_id": chunk_id,
            "source_file": os.path.relpath(source_file, ROOT).replace("\\", "/"),
            "case_name": case_name,
            "doc_type": doc_type,
            "doc_subtype": doc_subtype,
            "page_or_section": page_or_section,
            "section_context": clean(section_context) if section_context else None,
            "topic_tags": tag_topics(tagging_text),
            "consulting_tags": consulting_tags(doc_type, tagging_text),
            "content_summary": text[:200],
            "text_len": len(text),
            "evidence_status": evidence_status,
            "extraction_quality": "noise_suspected" if noise else extraction_quality,
            "engine_link": engine_link_for(doc_type, tagging_text),
            "duplicate_of": duplicate_of,
        }
        specs, costs = extract_spec_cost(text)
        rec["spec_values"] = specs
        rec["cost_values"] = costs
        rec["spec_signal"] = bool(specs)
        rec["cost_signal"] = bool(costs)
        self.chunks.append(rec)

    def skip(self, path, reason):
        self.skipped_files.append((os.path.relpath(path, ROOT).replace("\\", "/"), reason))


def chunk_pdf_by_page(w, path, case_name, doc_type, doc_subtype, evidence_status="실측",
                       quality_note=None, duplicate_of=None):
    # 페이지 단위(도면·시방서·구조계산 등)는 pypdf로 텍스트만 빠르게 추출한다.
    # pdfplumber는 벡터가 많은 도면 PDF에서 페이지당 수십 초~수 분이 걸려 비현실적이다.
    # pypdf 추출이 통째로 비면(스캔 등) pdfplumber로 폴백한다.
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        pages = reader.pages
        n_pages = len(pages)
        n_blank = 0
        got_any = False
        for i, page in enumerate(pages):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if not t.strip():
                n_blank += 1
                continue
            got_any = True
            w.add(case_name, doc_type, doc_subtype, path, f"p{i+1}", t,
                  evidence_status=evidence_status,
                  extraction_quality=quality_note or "normal",
                  duplicate_of=duplicate_of)
        if got_any or n_pages == 0:
            return n_pages, n_blank
    except Exception:
        pass
    # 폴백: pdfplumber
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        n_blank = 0
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            if not t.strip():
                n_blank += 1
                continue
            w.add(case_name, doc_type, doc_subtype, path, f"p{i+1}", t,
                  evidence_status=evidence_status,
                  extraction_quality=quality_note or "normal",
                  duplicate_of=duplicate_of)
    return n_pages, n_blank


def chunk_pdf_table_or_lines(w, path, case_name, doc_type, doc_subtype, evidence_status="실측",
                              duplicate_of=None):
    n_pages_with_table = 0
    n_pages_line_fallback = 0
    current_section = None
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                n_pages_with_table += 1
                for ti, table in enumerate(tables):
                    for ri, row in enumerate(table):
                        cells = [clean(c) for c in row if c]
                        if not cells:
                            continue
                        row_text = " | ".join(cells)
                        if len(row_text) < 2:
                            continue
                        if is_header_row(cells):
                            current_section = row_text
                            ctx = None
                        else:
                            ctx = current_section
                        w.add(case_name, doc_type, doc_subtype, path, f"p{i+1}-t{ti+1}-r{ri+1}",
                              row_text, evidence_status=evidence_status,
                              extraction_quality="table_extract", duplicate_of=duplicate_of,
                              section_context=ctx)
            else:
                t = page.extract_text() or ""
                if not t.strip():
                    continue
                n_pages_line_fallback += 1
                for li, line in enumerate(t.split("\n")):
                    if len(line.strip()) < 2:
                        continue
                    if is_header_row([line.strip()]):
                        current_section = line.strip()
                        ctx = None
                    else:
                        ctx = current_section
                    w.add(case_name, doc_type, doc_subtype, path, f"p{i+1}-line{li+1}",
                          line, evidence_status=evidence_status,
                          extraction_quality="line_fallback", duplicate_of=duplicate_of,
                          section_context=ctx)
    return n_pages_with_table, n_pages_line_fallback


def chunk_xlsx(w, path, case_name, doc_type, doc_subtype, evidence_status="실측"):
    wb = openpyxl.load_workbook(path, data_only=True)
    n_rows = 0
    for ws in wb.worksheets:
        current_section = None
        for ri, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = [str(c) for c in row if c is not None and str(c).strip()]
            if not cells:
                continue
            row_text = " | ".join(cells)
            if len(row_text) < 2:
                continue
            n_rows += 1
            if is_header_row(cells):
                current_section = row_text
                ctx = None
            else:
                ctx = current_section
            w.add(case_name, doc_type, doc_subtype, path, f"{ws.title}-r{ri}",
                  row_text, evidence_status=evidence_status, extraction_quality="xlsx_row",
                  section_context=ctx)
    return n_rows


def chunk_xls_legacy(w, path, case_name, doc_type, doc_subtype, evidence_status="실측"):
    import pandas as pd
    n_rows = 0
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None, engine="xlrd")
    except Exception as e:
        w.skip(path, f"xls 읽기 실패: {e}")
        return 0
    for sheet_name, df in sheets.items():
        current_section = None
        for ri, row in df.iterrows():
            cells = [str(c) for c in row.tolist() if str(c) not in ("nan", "None", "")]
            if not cells:
                continue
            row_text = " | ".join(cells)
            if len(row_text) < 2:
                continue
            n_rows += 1
            if is_header_row(cells):
                current_section = row_text
                ctx = None
            else:
                ctx = current_section
            w.add(case_name, doc_type, doc_subtype, path, f"{sheet_name}-r{ri+1}",
                  row_text, evidence_status=evidence_status, extraction_quality="xls_row",
                  section_context=ctx)
    return n_rows


def chunk_docx(w, path, case_name, doc_type, doc_subtype, evidence_status="실측"):
    import docx
    d = docx.Document(path)
    n = 0
    current_section = None
    HEADING_STYLES = {"Heading 1", "Heading 2", "Heading 3", "Title"}
    for pi, para in enumerate(d.paragraphs):
        t = clean(para.text)
        if len(t) < 2:
            continue
        is_heading = para.style.name in HEADING_STYLES or bool(SECTION_HEADER_PATTERN.match(t))
        if is_heading:
            current_section = t
            ctx = None
        else:
            ctx = current_section
        n += 1
        w.add(case_name, doc_type, doc_subtype, path, f"para{pi+1}", t,
              evidence_status=evidence_status, extraction_quality="docx_para",
              section_context=ctx)
    for ti, table in enumerate(d.tables):
        for ri, row in enumerate(table.rows):
            cells = [clean(c.text) for c in row.cells if clean(c.text)]
            if not cells:
                continue
            row_text = " | ".join(cells)
            n += 1
            w.add(case_name, doc_type, doc_subtype, path, f"t{ti+1}-r{ri+1}",
                  row_text, evidence_status=evidence_status, extraction_quality="docx_table_row")
    return n


def write_outputs(w, jsonl_path, summary_path, extra_log=None):
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in w.chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    from collections import Counter
    by_doc_type = Counter(c["doc_type"] for c in w.chunks)
    by_case = Counter(c["case_name"] for c in w.chunks)
    by_quality = Counter(c["extraction_quality"] for c in w.chunks)
    topic_counter = Counter()
    for c in w.chunks:
        for t in c["topic_tags"]:
            topic_counter[t] += 1
    untagged = sum(1 for c in w.chunks if not c["topic_tags"])
    linked = sum(1 for c in w.chunks if c["engine_link"])
    consult_counter = Counter()
    for c in w.chunks:
        for t in c.get("consulting_tags", []):
            consult_counter[t] += 1
    spec_n = sum(1 for c in w.chunks if c.get("spec_signal"))
    cost_n = sum(1 for c in w.chunks if c.get("cost_signal"))

    with open(summary_path, "w", encoding="utf-8") as f:
        if extra_log:
            f.write("=== 처리 로그 ===\n")
            for line in extra_log:
                f.write(line + "\n")
            f.write("\n")

        f.write(f"=== 총 청크 수: {len(w.chunks)} ===\n")
        f.write(f"=== 처리 실패/건너뛴 파일 수: {len(w.skipped_files)} ===\n")

        f.write("\n-- doc_type별 청크 수 --\n")
        for k, v in by_doc_type.most_common():
            f.write(f"  {k}: {v}\n")
        f.write("\n-- case별 청크 수 (상위 30) --\n")
        for k, v in by_case.most_common(30):
            f.write(f"  {k}: {v}\n")
        f.write("\n-- extraction_quality별 청크 수 --\n")
        for k, v in by_quality.most_common():
            f.write(f"  {k}: {v}\n")
        f.write("\n-- 주제축별 태깅 건수 (청크 1개가 복수 축에 걸릴 수 있음) --\n")
        for k, v in topic_counter.most_common():
            f.write(f"  {k}: {v}\n")
        f.write(f"\n미분류(태그 0개) 청크 수: {untagged} / {len(w.chunks)}"
                f" ({untagged/len(w.chunks)*100:.1f}%)\n" if w.chunks else "\n청크 없음\n")
        f.write(f"\nengine_link 있음: {linked} / {len(w.chunks)}\n")

        f.write("\n-- 컨설팅단계별 태깅 건수 (복수 단계 가능) --\n")
        for k in ["진단", "설계", "비용최적화", "운영최적화", "유지보수"]:
            f.write(f"  {k}: {consult_counter.get(k, 0)}\n")
        f.write(f"\n성능사양 수치 포함(spec_signal) 청크: {spec_n} / {len(w.chunks)}\n")
        f.write(f"비용 수치 포함(cost_signal) 청크: {cost_n} / {len(w.chunks)}\n")

        if w.skipped_files:
            f.write("\n-- 건너뛴 파일 (근거 없이 채우지 않고 명시적으로 제외) --\n")
            for path, reason in w.skipped_files:
                f.write(f"  {path}: {reason}\n")

    print(f"완료: 청크 {len(w.chunks)}개 -> {jsonl_path}")
    print(f"건너뛴 파일 {len(w.skipped_files)}개")
    print(f"요약 -> {summary_path}")
