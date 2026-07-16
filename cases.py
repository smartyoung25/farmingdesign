"""
케이스 레지스트리 로더 (P0 근거대장 최소본 흡수)
- cases/*.json = 농가별 입력(input) + 근거·기준시점(provenance, as_of).
- 계산은 하지 않는다. FarmInput 으로 변환만 하고, 계산은 엔진(render_report.compute)이 한다.
- 빈 파일/불량 JSON/필수키 없는 파일은 건너뛴다(삭제 불가 환경의 tombstone 대응).
"""
from __future__ import annotations
import json, glob, os
import smartfarm_engine as e
from run_report import FarmInput

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")


def load_cases() -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*.json"))):
        try:
            if os.path.getsize(path) == 0:
                continue
            with open(path, encoding="utf-8") as f:
                c = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(c, dict) and c.get("case_id") and isinstance(c.get("input"), dict):
            out.append(c)
    return out


def case_to_input(case: dict) -> FarmInput:
    d = dict(case["input"])
    d["business_type"] = e.BusinessType(d["business_type"])
    d["cover"] = e.Cover(d["cover"])
    return FarmInput(**d)
