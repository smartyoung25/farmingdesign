"""272차 뮤테이션 — 지역 정규화 재측정 가드(test_272cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 272
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '272cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_지역정규화_기상지점_20260929.md'
E = 'smartfarm_engine.py'
M = [
 ("M1 도달 수만 문서에서 고침", D, "| **못 닿는 행정구역** | **103** |", "| **못 닿는 행정구역** | **100** |"),
 ("M2 이름 일치 수 틀림", D, "| 이름이 같은 것 | **66** |", "| 이름이 같은 것 | **69** |"),
 ("M3 별칭을 지워 도달을 떨어뜨림", E, 'WEATHER_STATION_ALIASES = {"마산": "창원", "창원": "마산"}',
  'WEATHER_STATION_ALIASES = {}'),
 ("M4 괄호 규칙을 몰래 적용(241차 결정 변경)", E, "cands = {k for k in table if k in region}",
  "cands = {k for k in table if k in region} if '(' not in region else set()"),
 ("M5 241차 한계 주석 삭제", E, "알려진 한계: 부분 일치는 **글자 포함**이라", "한계 없음: 부분 일치는 글자 포함이라"),
 ("M6 「바꾸지 않았다」를 뒤집음", D, "**272차는 아무것도 바꾸지 않았다.**", "272차가 괄호 규칙을 적용했다."),
 ("M7 결함이라고 단정", D, "결함이 아니라 결정의 대가", "명백한 결함"),
 ("M8 원문 표를 찾았다고 바꿈", D, "## 2. 원문 표를 찾았나 — **찾지 못했다**", "## 2. 원문 표를 찾았다"),
 ("M9 별표1 오용 경고 삭제", D, "**근거의 오용**이다", "그대로 쓰면 된다"),
 ("M10 ASOS 역방향 한계 삭제", D, "**역방향(172 시군구 → 지점)은 주지 않는다**", "역방향도 준다"),
 ("M11 88차 선행 기록 삭제", D, "**새 발견이 아니다**", "새 발견이다"),
 ("M12 별표7 인용을 원문 대조로 승격", D, "**검색 결과 인용**이고 원문 대조가 아니다", "원문 대조로 확인했다"),
 ("M13 어느 광주인지 단정", D, "어느 쪽이 맞는지는 말하지 않는다", "광주광역시가 맞다"),
 ("M14 2차 표기 제거", D, "**[2차·미확인]**", "**[1차]**"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
