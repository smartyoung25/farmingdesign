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
  python3 run_chunk_incremental.py --view      # 정본 인덱스 ⊕ 오버레이 → 뷰 파일 생성
  python3 run_chunk_incremental.py --retag-only # 키워드 개정 시 재추출 없이 태그만 재계산
반복 실행하면 남은 파일만 이어서 처리한다(멱등).

P2-14(2026-08-17): 매니페스트(청킹_매니페스트.json) 기반 4상태 diff를 도입했다 —
종전엔 파트파일 존재 여부만 봐서 원본 변경·삭제를 감지하지 못했으나, 이제
지문(sha256+mtime/size) 대조로 무변경은 건너뛰고 변경은 재청킹, 삭제는 tombstone
표시한다. 파일 1건 처리마다 매니페스트를 원자적으로 체크포인트한다.
주의: SHARD 병렬 실행 시 매니페스트는 프로세스별 저장이라 마지막 저장이 이긴다 —
병렬이 필요하면 매니페스트 병합은 미지원(현 환경은 단일 프로세스라 문제 없음).
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
    MANIFEST_PATH, OVERLAY_PATH, file_fingerprint, load_manifest, save_manifest,
    classify_file_states, load_overlay, apply_overlay,
    tag_topics, tag_domains_b, consulting_tags, engine_link_for,
)

PARTS = os.path.join(ROOT, "_chunks_parts_9축")
os.makedirs(PARTS, exist_ok=True)
SEEN = os.path.join(PARTS, "_seen_hashes.json")
BUDGET = float(os.environ.get("CHUNK_BUDGET", "35"))
RUN_ID = time.strftime("%Y-%m-%dT%H%M%S")


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
        return "already", 0, None
    basename = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    rec = {"relpath": rel, "chunks": [], "skips": [], "run_id": RUN_ID}

    if basename.startswith("~$"):
        rec["skips"].append([rel, "엑셀 락파일(임시)"])
        dump(part, rec); return "lockfile", 0, rec
    if ext in full.SKIP_EXT:
        reason = {".hwp": "HWP 텍스트 추출 도구 없음(2026-07-23 확인)",
                  ".doc": "구버전 워드(.doc) — python-docx로 못 읽음"}.get(ext, "이미지 파일(OCR 미적용)")
        rec["skips"].append([rel, reason])
        dump(part, rec); return "skip_ext", 0, rec

    result = full.classify(path)
    if result is None:
        rec["skips"].append([rel, "스코프 제외 폴더(노지/대산온실) 또는 락파일"])
        dump(part, rec); return "excluded", 0, rec
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
    for c in rec["chunks"]:
        c["first_seen_run"] = RUN_ID  # P2-14: 실행 버전 태깅(방법론 6-6절)
    rec["skips"].extend(list(s) for s in full.W.skipped_files)
    dump(part, rec)
    return "ok", len(rec["chunks"]), rec


def manifest_entry_from(rec, fp, prev=None, first_seen=None):
    """파트 처리 결과(rec)와 지문(fp)으로 매니페스트 항목을 만든다(방법론 6-1절)."""
    chunks = rec.get("chunks", [])
    skips = rec.get("skips", [])
    if chunks:
        status = "processed"
    elif skips and str(skips[0][1]).startswith("처리 중 예외"):
        status = "error"
    else:
        status = "skipped"
    return {
        "sha256": fp["sha256"], "mtime": fp["mtime"], "size": fp["size"],
        "status": status,
        "doc_type": rec.get("doc_type"), "case_name": rec.get("case"),
        "chunk_count": len(chunks),
        "first_seen_run": first_seen or (prev or {}).get("first_seen_run") or RUN_ID,
        "last_seen_run": RUN_ID,
        "skip_reason": (str(skips[0][1]) if skips and not chunks else None),
    }


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
    extra = [f"증분 병합: 처리파일 {len(recs)}개 → 청크 {len(w.chunks)}개"]
    # P2-14: 삭제 감지(tombstone) 보고 — 청크는 지우지 않고 추적성만 남긴다(방법론 6-2절)
    manifest = load_manifest()
    tombs = [rel for rel, e in manifest["files"].items() if e.get("status") == "tombstoned"]
    if tombs:
        extra.append(f"tombstoned(원본 삭제됨, 청크는 보존) {len(tombs)}건: " + " · ".join(tombs))
    overlay = load_overlay()
    if overlay:
        extra.append(f"오버레이 보정 {len(overlay)}건 존재 — 뷰 생성은 --view (정본 인덱스는 자동태깅 순수본 유지)")
    write_outputs(
        w,
        index_path,
        os.path.join(ROOT, "문서청킹_전체_요약_9축.txt"),
        extra_log=extra,
    )
    print(f"MERGED files={len(recs)} chunks={len(w.chunks)} skips={len(w.skipped_files)}", flush=True)


def retag_only():
    """P2-15 — 키워드 개정 시 재추출 없이 태그 필드만 재계산(방법론 9-2절).

    파트에 보존된 태깅 원문(`_tag_text`)으로 topic_tags(Layer A)·domain_tags_B
    (Layer B)·consulting_tags·engine_link를 다시 계산해 파트를 원자적으로
    갱신한다. L2 행(chunk_level=='row')은 무태깅 규칙 유지. `_tag_text`가 없는
    구세대 청크는 section_context+content_summary(200자 절단)로 근사 재태깅하고
    개수를 보고한다(장문 청크에선 손실 가능 — 정밀 재태깅이 필요하면 해당 파일
    파트를 지워 재추출). 이후 --merge 로 정본을 다시 만든다."""
    n_parts = n_chunks = n_fallback = 0
    for p in sorted(glob.glob(os.path.join(PARTS, "*.part.json"))):
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
        changed = False
        for c in rec.get("chunks", []):
            n_chunks += 1
            tag_text = c.get("_tag_text")
            if tag_text is None:
                tag_text = ((c.get("section_context") or "") + " " + (c.get("content_summary") or "")).strip()
                n_fallback += 1
            suppressed = c.get("chunk_level") == "row"
            new_vals = {
                "topic_tags": [] if suppressed else tag_topics(tag_text),
                "domain_tags_B": [] if suppressed else tag_domains_b(tag_text),
                "consulting_tags": consulting_tags(c.get("doc_type"), tag_text),
                "engine_link": engine_link_for(c.get("doc_type"), tag_text),
            }
            for k, v in new_vals.items():
                if c.get(k) != v:
                    c[k] = v
                    changed = True
        if changed:
            dump(p, rec)
            n_parts += 1
    print(f"RETAG parts_updated={n_parts} chunks={n_chunks} fallback_no_tag_text={n_fallback}", flush=True)
    if n_fallback:
        print(f"경고: _tag_text 없는 청크 {n_fallback}건은 200자 절단 근사 재태깅 — "
              "정밀 재태깅이 필요하면 해당 파일 파트 삭제 후 재추출", flush=True)
    print("다음 단계: python run_chunk_incremental.py --merge", flush=True)


def view():
    """정본 인덱스 ⊕ 오버레이 → 최종 뷰 파일(방법론 6-4절). 정본은 불변."""
    index_path = os.path.join(ROOT, "문서청킹_인덱스_전체_9축.jsonl")
    view_path = os.path.join(ROOT, "문서청킹_인덱스_전체_9축_오버레이뷰.jsonl")
    overlay = load_overlay()
    if not overlay:
        print("오버레이 보정 0건 — 뷰 생성 생략(정본 인덱스가 곧 최종 뷰). "
              "보정은 청킹_오버레이.jsonl에 {\"chunk_id\":…, \"source_file\":…, \"fields\":{…}} 형식으로 추가", flush=True)
        return
    chunks = []
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    merged, n_applied, n_unmatched = apply_overlay(chunks, overlay)
    with open(view_path, "w", encoding="utf-8") as f:
        for c in merged:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"VIEW chunks={len(merged)} overlay_entries={len(overlay)} "
          f"applied={n_applied} unmatched={n_unmatched} -> {view_path}", flush=True)
    if n_unmatched:
        print("경고: 미매칭 오버레이 존재 — chunk_id/source_file 오타 또는 원본 재청킹으로 id가 바뀐 항목", flush=True)


def main():
    args = sys.argv[1:]
    if "--merge" in args:
        merge(); return
    if "--view" in args:
        view(); return
    if "--retag-only" in args:
        retag_only(); return
    assert_pipeline_dependencies()  # P2-23: 처리 시작 전 필수 파서 존재 확인
    if "all" in args:
        bases = [full.SPEC_DIR, full.FACILITY_DIR]
    elif "facility" in args:
        bases = [full.FACILITY_DIR]
    else:
        bases = [full.SPEC_DIR]  # 기본: 스마트팜스펙 (사용자 지정 시방서/설계서/견적서/도면)

    files = gather(bases)
    total = len(files)

    # ── P2-14: 매니페스트 4상태 diff (방법론 6-2절) ──
    manifest = load_manifest()
    mf = manifest["files"]
    current = {}
    for p in files:
        rel = relpath(p)
        st = os.stat(p)
        ent = mf.get(rel)
        # 최적화: mtime+size가 매니페스트와 같으면 저장된 sha256 재사용(내용이 같은데
        # mtime·size까지 조작된 경우만 놓친다 — 실무상 무시 가능. CHUNK_FULL_HASH=1로 전량 해시 강제)
        if (ent and os.environ.get("CHUNK_FULL_HASH") != "1"
                and ent.get("mtime") == st.st_mtime_ns and ent.get("size") == st.st_size
                and ent.get("sha256")):
            current[rel] = {"sha256": ent["sha256"], "mtime": st.st_mtime_ns, "size": st.st_size}
        else:
            current[rel] = file_fingerprint(p)
    states = classify_file_states(current, mf)

    # 삭제 감지 → tombstone(청크·파트는 지우지 않음, 추적성 보존)
    for rel in states["deleted"]:
        mf[rel]["status"] = "tombstoned"
        print(f"tombstone: {rel} (원본 삭제 감지 — 청크는 인덱스에 보존)", flush=True)

    # 변경 감지 → 파트 무효화(삭제) 후 재처리 대상으로
    for rel in states["changed"]:
        part = part_path(rel)
        if os.path.exists(part):
            os.remove(part)
        print(f"changed: {rel} (지문 불일치 — 재청킹 예정)", flush=True)

    # 신규 중 파트가 이미 있는 파일 = 매니페스트 도입 전(pre-manifest) 처리분 → 재청킹 없이 대장에 편입
    adopted = 0
    for rel in list(states["new"]):
        part = part_path(rel)
        if os.path.exists(part):
            with open(part, encoding="utf-8") as f:
                rec = json.load(f)
            mf[rel] = manifest_entry_from(rec, current[rel], first_seen="pre-manifest(≤2026-08-17)")
            states["new"].remove(rel)
            states["unchanged"].append(rel)  # 이후 로직에선 무변경과 동일 취급
            adopted += 1

    # 자기치유: 매니페스트상 무변경인데 파트가 없으면(파트 수동 삭제·유실·태깅로직
    # 개정을 위한 강제 재처리) 재처리 대상에 넣는다 — 매니페스트와 파트의 불일치를
    # 조용히 방치하지 않는다.
    healed = [rel for rel in states["unchanged"] if not os.path.exists(part_path(rel))]

    # 무변경 → last_seen_run만 갱신(재청킹 없음 — 방법론 6-2절 핵심)
    for rel in states["unchanged"]:
        if rel in mf:
            mf[rel]["last_seen_run"] = RUN_ID

    manifest["last_run"] = RUN_ID
    save_manifest(manifest)
    print(f"scope files={total} | diff: unchanged={len(states['unchanged'])}"
          f"(adopted={adopted}, part유실 재처리={len(healed)}) new={len(states['new'])}"
          f" changed={len(states['changed'])} deleted={len(states['deleted'])}"
          f" | run={RUN_ID} budget={BUDGET}s", flush=True)

    # ── 처리 루프: 신규+변경+파트유실 (샤딩: SHARD="i/N" — 매니페스트 병렬 병합은 미지원, 주의) ──
    todo = sorted(set(states["new"]) | set(states["changed"]) | set(healed))
    shard = os.environ.get("SHARD")
    si, sn = 0, 1
    if shard and "/" in shard:
        si, sn = (int(x) for x in shard.split("/"))

    start = time.time()
    counts = {}
    for i, rel in enumerate(todo):
        if sn > 1 and (i % sn) != si:
            continue
        if time.time() - start > BUDGET:
            save_manifest(manifest)
            print(f"COUNTS: {json.dumps(counts, ensure_ascii=False)}", flush=True)
            print("STATUS: MORE", flush=True)
            return
        path = os.path.join(ROOT, rel)
        status, n, rec = process_one(path)
        counts[status] = counts.get(status, 0) + 1
        if rec is not None:
            mf[rel] = manifest_entry_from(rec, current[rel], prev=mf.get(rel))
            save_manifest(manifest)  # 파일 1건마다 체크포인트(방법론 6-5절)
        if status == "ok":
            print(f"[{i+1}/{len(todo)}] ok +{n}  {rel}", flush=True)
    save_manifest(manifest)
    print(f"COUNTS: {json.dumps(counts, ensure_ascii=False)}", flush=True)
    print("STATUS: COMPLETE", flush=True)


if __name__ == "__main__":
    main()
