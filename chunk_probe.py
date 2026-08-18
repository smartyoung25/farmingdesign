"""청킹 인덱스 read-only 검색 로더 (2026-08-18, 41차) — 59,509청크의 첫 코드 소비자.

원칙 5 준수(구조로 강제): 이 모듈은 검색·원문 역추적 **전용**이다.
- 수치 집계·계산 기능을 두지 않는다(청킹 인덱스는 검색 계층일 뿐 제2의 계산 출처가
  아니다 — 청크 값의 엔진 승격은 기존 절차[원문 확인→레지스트리→드리프트 가드]로만).
- smartfarm_engine·build_site·webapp는 이 모듈을 import하지 않는다(테스트로 고정).
- 기존 수동 프로브 관행(P2-17 윤성호 발굴, 26차 물향기 확정, P3-21c 카톡 분류)의
  도구화 — 신기능이 아니라 3회 이상 실증된 워크플로의 정착.

사용:
  python chunk_probe.py --keyword 윤성호 --limit 10
  python chunk_probe.py --doc-type 공사비내역서 --case 우민재
  python chunk_probe.py --engine-link SPEC_TABLE
  python chunk_probe.py --chunk-id 제도문서_시방서__p1     (원문 역추적)
"""
import argparse
import io
import json
import os
import sys

INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "문서청킹_인덱스_전체_9축.jsonl")

# probe가 돌려주는 필드(선별) — 전체 청크가 필요하면 raw=True
RESULT_FIELDS = ("chunk_id", "source_file", "case_name", "doc_type", "doc_subtype",
                 "page_or_section", "content_summary", "engine_link", "topic_tags",
                 "domain_tags_B", "evidence_status", "extraction_quality")


def iter_chunks(index_path: str = INDEX_PATH):
    """정본 인덱스 스트리밍(53MB 전체 메모리 로드 회피). 손상 행은 건너뛰지 않고
    예외를 그대로 낸다 — 정본 오염은 조용히 넘어가지 않는다."""
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def probe(keyword: str = None, doc_type: str = None, case: str = None,
          engine_link: str = None, chunk_id: str = None,
          limit: int = 20, raw: bool = False, index_path: str = INDEX_PATH) -> list:
    """조건 AND 검색 — keyword는 content_summary·source_file·chunk_id·topic_tags에
    대해 부분일치(대소문자 무시), doc_type/case는 정확일치, engine_link는 부분일치.
    반환: 선별 필드 dict 리스트(limit개까지). 집계·합산 없음."""
    kw = keyword.lower() if keyword else None
    out = []
    for c in iter_chunks(index_path):
        if chunk_id is not None and c.get("chunk_id") != chunk_id:
            continue
        if doc_type is not None and c.get("doc_type") != doc_type:
            continue
        if case is not None and c.get("case_name") != case:
            continue
        if engine_link is not None:
            el = str(c.get("engine_link") or "")
            if engine_link not in el:
                continue
        if kw is not None:
            hay = " ".join([str(c.get("content_summary") or ""), str(c.get("source_file") or ""),
                            str(c.get("chunk_id") or ""), " ".join(c.get("topic_tags") or [])]).lower()
            if kw not in hay:
                continue
        out.append(dict(c) if raw else {k: c.get(k) for k in RESULT_FIELDS})
        if len(out) >= limit:
            break
    return out


def trace(chunk_id: str, index_path: str = INDEX_PATH) -> dict:
    """청크 id → 원문 위치(source_file·page_or_section 등). 없으면 None."""
    hits = probe(chunk_id=chunk_id, limit=1, raw=True, index_path=index_path)
    if not hits:
        return None
    c = hits[0]
    return {"chunk_id": c["chunk_id"], "source_file": c["source_file"],
            "page_or_section": c.get("page_or_section"),
            "doc_type": c.get("doc_type"), "case_name": c.get("case_name"),
            "extraction_quality": c.get("extraction_quality"),
            "source_exists": os.path.isfile(os.path.join(os.path.dirname(index_path),
                                                         c["source_file"]))}


def main(argv=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="청킹 인덱스 read-only 검색(집계·계산 없음)")
    ap.add_argument("--keyword")
    ap.add_argument("--doc-type", dest="doc_type")
    ap.add_argument("--case")
    ap.add_argument("--engine-link", dest="engine_link")
    ap.add_argument("--chunk-id", dest="chunk_id")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args(argv)
    if a.chunk_id:
        print(json.dumps(trace(a.chunk_id), ensure_ascii=False, indent=1))
        return
    hits = probe(keyword=a.keyword, doc_type=a.doc_type, case=a.case,
                 engine_link=a.engine_link, limit=a.limit)
    for h in hits:
        print(f"- {h['chunk_id']} | {h['doc_type']} | {h['source_file']} "
              f"| {h.get('page_or_section')} | {str(h.get('content_summary'))[:80]}")
    print(f"({len(hits)}건 — limit {a.limit})")


if __name__ == "__main__":
    main()
