"""242차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 242  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, CP, W = 'smartfarm_engine.py', 'consulting_package.py', 'webapp.py'
M = [
 ("M1 검증 순서 되돌림(지점 없으면 13월 통과)", E,
  '    ms = list(months)\n    if not ms:\n        raise ValueError("months가 비어 있다 — 평균 낼 달을 지정해야 한다")\n    if any((not isinstance(m, int)) or m < 1 or m > 12 for m in ms):\n        raise ValueError(f"months는 1~12 정수여야 한다: {months!r}")\n    row = MONTHLY_MEAN_WIND_MS.get(_weather_key(MONTHLY_MEAN_WIND_MS, region))   # 241차\n    if row is None:\n        return None\n',
  '    row = MONTHLY_MEAN_WIND_MS.get(_weather_key(MONTHLY_MEAN_WIND_MS, region))   # 241차\n    if row is None:\n        return None\n    ms = list(months)\n    if not ms:\n        raise ValueError("months가 비어 있다 — 평균 낼 달을 지정해야 한다")\n    if any((not isinstance(m, int)) or m < 1 or m > 12 for m in ms):\n        raise ValueError(f"months는 1~12 정수여야 한다: {months!r}")\n'),
 ("M2 기본 동절기 도입(12·1·2)", E, 'def mean_wind(region: str, months) -> Optional[float]:', 'def mean_wind(region: str, months=(12, 1, 2)) -> Optional[float]:'),
 ("M3 저장 블록을 패키지가 안 읽음", CP, '    if sc.get("winter_months"):\n', '    if False:\n'),
 ("M4 한 달 지정 거부", W, '    if not months:\n        raise HTTPException(400, detail="동절기 달을 한 달 이상',
  '    if len(months) < 2:\n        raise HTTPException(400, detail="동절기 달을 한 달 이상'),
 ("M5 근거 검사 제거", W, '    if not block["note"]:\n        raise HTTPException(400, detail="근거(note: 동절기',
  '    if False:\n        raise HTTPException(400, detail="근거(note: 동절기'),
 ("M6 스크린 미선택 허용", W, '    if scr not in ("yes", "no"):\n', '    if False:\n'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    crlf = '\r\n' in s
    a2 = a.replace('\n', '\r\n') if crlf else a
    b2 = b.replace('\n', '\r\n') if crlf else b
    if s.count(a2) != 1:
        res.append((name, f"적용 불가({s.count(a2)})")); continue
    open(f, 'wb').write(s.replace(a2, b2).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', 'test_engine.py', '-q', '-x',
                            '-k', '242cha or mean_wind or 241cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
