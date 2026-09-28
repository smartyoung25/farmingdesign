"""241차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 241  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
E, CP, R = 'smartfarm_engine.py', 'consulting_package.py', '엔진데이터_레지스트리.json'
M = [
 ("M1 별칭 한쪽만(마산→창원만)", E, 'WEATHER_STATION_ALIASES = {"마산": "창원", "창원": "마산"}', 'WEATHER_STATION_ALIASES = {"마산": "창원"}'),
 ("M2 애매해도 하나 고름", E, '    return next(iter(cands)) if len(cands) == 1 else None', '    return sorted(cands)[0] if cands else None'),
 ("M3 부분 일치 제거(현행 복귀)", E, '    cands = {k for k in table if k in region}\n', '    cands = set()\n'),
 ("M4 풍속만 부분 일치 누락", E, '    return MONTHLY_MEAN_WIND_MS.get(_weather_key(MONTHLY_MEAN_WIND_MS, region))', '    return MONTHLY_MEAN_WIND_MS.get(region)'),
 ("M5 D1 기상 지점 누락", CP, '                 "기상 지점": e.weather_station(region),\n', ''),
 ("M6 t_min 병기 누락", CP, '                 "케이스 최저온도 t_min(입력)": inp.t_min,\n', ''),
 ("M7 레지스트리 결정 문구 약화", R, '**후보가 둘 이상이면 None**', '후보 중 첫째'),
 ("M8 충남에 지점 지어냄(광역 대표)", E, '    alias = WEATHER_STATION_ALIASES.get(region)\n',
  '    if region == "충남":\n        return "천안"\n    alias = WEATHER_STATION_ALIASES.get(region)\n'),
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
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_cases.py', '-q', '-x',
                            '-k', '241cha or 96cha or 159cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
