"""
9축 문서청킹 — 재개(resume) 가능한 증분 실행 드라이버.

배경: 로컬 디바이스(브리지) 실행은 (1) 명령당 45초 제한, (2) 간헐적 연결 끊김이
있어 한 번에 전체 말뭉치를 처리하면 산출물이 유실된다. 이 드라이버는 파일 1개를
처리할 때마다 그 파일의 청크를 즉시 부분파일(`_chunks_parts_9축/<sha1>.part.json`)로
저장하고, 이미 처리된 파일은 건너뛴다. 매 호출은 시간예산(기본 35초) 안에서 가능한
만큼 처리하고 깨끗하게 종료(STATUS: MORE)하며, 전부 끝나면 STATUS: COMPLETE 를 낸다.

분류·청킹·태깅 로직은 `build_document_chunks_full_v2`(=파일럿 검증본 + 9축 개정)를
그대로 재사용한다 — 결과 스키마·doc_type·case·중복(MD5)·스킵 규칙이 원본과 동일하다.

사용:
  python3 run_chunk_incremental.py spec       # 스마트팜스펙/ 만 (기본값)
  python3 run_chunk_incremental.py facility   # 시설평가/ 만
  python3 run_chunk_incremental.py all        # 둘 다
  python3 run_chunk_incremental.py --merge     # 부분파일 → 최종 jsonl+요약 병합
반복 실행하면 남은 파일만 이어서 처리한다(멱등).
"""
import os
import sys
import json
import time
import glob
import hashlib

import build_document_chunks_full_v2 as full
from chunking_lib_v2 import (
    ROOT, ChunkWriter, write_outputs,
    assert_pipeline_dependencies, chunk_count_regression_guard,
)

PARTS = os.path.join(ROOT, "_chunks_parts_9축")
os.makedirs(PARTS, exist_ok=True)
SEEN = os.path.join(PARTS, "_seen_hashes.json")
BUDGET = float(os.environ.get("CHUNK_BUDGET", "35"))


def relpath(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def part_path(rel):
    return os.path.join(PARTS, hashlib.sha1(rel.encode("utf-8")).hexdigest() + ".part.json")


def dump(path, rec):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    os.replace(tmp, path)  # 원자적 저장 — 중간에 끊겨도 반쪽 파일이 안 남는다


def gather(bases):
    files = []
    for base in bases:
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in full.EXCLUDE_DIRS]
            for fn in fns:
                files.append(os.path.join(dp, fn))
    return sorted(files)


def load_seen():
    if os.path.exists(SEEN):
        try:
            return json.load(open(SEEN, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_seen(s):
    dump(SEEN, s)


def process_one(path):
    rel = relpath(path)
    part = part_path(rel)
    if os.path.exists(part):
        return "already", 0
    basename = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    rec = {"relpath": rel, "chunks": [], "skips": []}

    if basename.startswith("~$"):
        rec["skips"].append([rel, "엑셀 락파일(임시)"])
        dump(part, rec); return "lockfile", 0
    if ext in full.SKIP_EXT:
        reason = {".hwp": "HWP 텍스트 추출 도구 없음(2026-07-23 확인)",
                  ".doc": "구버전 워드(.doc) — python-docx로 못 읽음"}.get(ext, "이미지 파일(OCR 미적용)")
        rec["skips"].append([rel, reason])
        dump(part, rec); return "skip_ext", 0

    result = full.classify(path)
    if result is None:
        rec["skips"].append([rel, "스코프 제외 폴더(노지/대산온실) 또는 락파일"])
        dump(part, rec); return "excluded", 0
    case, doc_type = result

    try:
        rec["md5"] = full.md5_of(path)
    except Exception as e:
        rec["md5"] = None
        rec["skips"].append([rel, f"해시 계산 실패: {e}"])

    rec["case"] = case
    rec["doc_type"] = doc_type
    full.W = ChunkWriter()
    full.log = []
    full.process_file(path, case, doc_type)
    rec["chunks"] = full.W.chunks
    rec["skips"].extend(list(s) for s in full.W.skipped_files)
    dump(part, rec)
    return "ok", len(rec["chunks"])


def merge():
    assert_pipeline_dependencies()  # P2-23: 의존성 유실 상태의 병합도 차단
    recs = []
    for p in glob.glob(os.path.join(PARTS, "*.part.json")):
        try:
            recs.append(json.load(open(p, encoding="utf-8")))
        except Exception as e:
            print("WARN bad part", p, e, flush=True)
    recs.sort(key=lambda r: r.get("relpath", ""))
    w = ChunkWriter()
    seen = {}          # md5 -> 최초 relpath (정렬순서 기준으로 최초 1건만 청크 유지)
    n_dup = 0
    for r in recs:
        md5 = r.get("md5")
        rel = r.get("relpath", "")
        if md5 and md5 in seen:
            # 완전중복 파일: 청크는 버리고 중복 표식 1건만 남긴다(원본 로직과 동일 의미)
            dw = ChunkWriter()
            dw.add(r.get("case", "미상"), r.get("doc_type", "미분류"), "완전중복",
                   os.path.join(ROOT, rel), "-", "", evidence_status="실측",
                   extraction_quality="skipped_duplicate", duplicate_of=seen[md5])
            w.chunks.extend(dw.chunks)
            n_dup += 1
            continue
        if md5:
            seen[md5] = rel
        w.chunks.extend(r.get("chunks", []))
        for s in r.get("skips", []):
            w.skipped_files.append(tuple(s))
    print(f"merge: {len(recs)} parts, {n_dup} MD5-중복 처리", flush=True)
    index_path = os.path.join(ROOT, "문서청킹_인덱스_전체_9축.jsonl")
    # P2-23: 기존 정본보다 총량이 줄면 덮어쓰기 전에 중단(조용한 열화 차단)
    chunk_count_regression_guard(len(w.chunks), index_path)
    write_outputs(
        w,
        index_path,
        os.path.join(ROOT, "문서청킹_전체_요약_9축.txt"),
        extra_log=[f"증분 병합: 처리파일 {len(recs)}개 → 청크 {len(w.chunks)}개"],
    )
    print(f"MERGED files={len(recs)} chunks={len(w.chunks)} skips={len(w.skipped_files)}", flush=True)


def main():
    args = sys.argv[1:]
    if "--merge" in args:
        merge(); return
    assert_pipeline_dependencies()  # P2-23: 처리 시작 전 필수 파서 존재 확인
    if "all" in args:
        bases = [full.SPEC_DIR, full.FACILITY_DIR]
    elif "facility" in args:
        bases = [full.FACILITY_DIR]
    else:
        bases = [full.SPEC_DIR]  # 기본: 스마트팜스펙 (사용자 지정 시방서/설계서/견적서/도면)

    files = gather(bases)
    # 샤딩: SHARD="i/N" 이면 인덱스 i, i+N, i+2N ... 파일만 처리(병렬 실행용)
    shard = os.environ.get("SHARD")
    si, sn = 0, 1
    if shard and "/" in shard:
        si, sn = (int(x) for x in shard.split("/"))
    total = len(files)
    already = sum(1 for p in files if os.path.exists(part_path(relpath(p))))
    print(f"scope files={total}, already_done={already}, shard={si}/{sn}, budget={BUDGET}s", flush=True)

    start = time.time()
    counts = {}
    for i, path in enumerate(files):
        if sn > 1 and (i % sn) != si:
            continue
        if time.time() - start > BUDGET:
            print(f"COUNTS: {json.dumps(counts, ensure_ascii=False)}", flush=True)
            print("STATUS: MORE", flush=True)
            return
        status, n = process_one(path)
        counts[status] = counts.get(status, 0) + 1
        if status == "ok":
            print(f"[{i+1}/{total}] ok +{n}  {relpath(path)}", flush=True)
    print(f"COUNTS: {json.dumps(counts, ensure_ascii=False)}", flush=True)
    print("STATUS: COMPLETE", flush=True)


if __name__ == "__main__":
    main()
