# -*- coding: utf-8 -*-
"""문서청킹 파이프라인 가드 테스트 (P2-23, 2026-08-17).

엔진 회귀(test_engine/test_registry/test_cases)와 별개 트랙 — 청킹 실행 전
`python -m pytest test_chunking_v2.py -q`로 가드가 살아있는지 확인한다.
배경: 10-4절 xlrd 유실 사건(의존성 부재 → .xls 조용히 0청크 → 2,345청크 증발).
"""
import os

import pytest

from chunking_lib_v2 import (
    PIPELINE_DEPENDENCIES,
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
