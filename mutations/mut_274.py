"""274차 뮤테이션 — 괄호 장치 가드(test_274cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 274
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '274cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
E = 'smartfarm_engine.py'
R = '엔진데이터_레지스트리.json'
D = '근거_지역정규화_기상지점_20260929.md'
M = [
 ("M1 규칙을 꺼 버림", E, '"skip_when_bracket_is_province": True,', '"skip_when_bracket_is_province": False,'),
 ("M2 첫 규칙으로 되돌림(괄호면 무조건 차단)", E,
  'if any(t in prov for t in _bracket_texts(region, r.get("bracket_pairs", ()))):',
  'if any(b in region for b, _ in r.get("bracket_pairs", ())):'),
 ("M3 광역 목록에 지점명 섞음", E, '"경기", "강원", "충북",', '"경기", "강원", "춘천", "충북",'),
 ("M4 광역 하나 빠뜨림", E, '"경기", "강원", "충북", "충남",', '"경기", "강원", "충북",'),
 ("M5 주입 경로 제거", E, "    r = WEATHER_MATCH_RULE if rule is None else rule",
  "    r = WEATHER_MATCH_RULE"),
 ("M6 괄호 내용 추출을 통째로 무력화", E, "            out.append(part[i + 1:j].strip())",
  "            out.append('')"),
 ("M7 레지스트리 status 강등", R, '"status_note": "결정(★사용자 2026-09-29, WO-010',
  '"status_note": "추정(★사용자 2026-09-29, WO-010'),
 ("M8 레지스트리 근거 인용 삭제", R, "근거_지역정규화_기상지점_20260929.md` 4절",
  "어딘가에 적힌 결정"),
 ("M9 241차 한계 주석 삭제", E, "알려진 한계: 부분 일치는 **글자 포함**이라",
  "한계 없음: 부분 일치는 글자 포함이라"),
 ("M10 274차 기록 삭제", E, "274차 — 그 한계를 막았다", "그 한계는 남아 있다"),
 ("M11 엔진 주석에 ★ 유입", E, "#   사용자 결정 2026-09-29: **애매하면 안 준다**",
  "#   ★사용자 결정 2026-09-29: **애매하면 안 준다**"),
 ("M12 첫 규칙이 깬 기록 삭제", D, "첫 규칙이 케이스 둘을 깼다", "규칙은 한 번에 맞았다"),
 ("M13 두 뜻 표에서 하위 지명 행 삭제", D,
  "| `강원(춘천)` | 춘천 | **하위 지명**(지점 이름) | 아니다 |",
  "| `강원(춘천)` | 춘천 | 광역 한정자 | 그렇다 |"),
 ("M14 103지역 결정 삭제", D, "103지역은 잇지 않는다", "103지역을 이었다"),
 ("M15 272차 시점 표기 삭제", D, "위 수는 272차 시점이다", "이 수는 언제나 맞다"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
