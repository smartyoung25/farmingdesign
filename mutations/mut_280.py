"""280차 뮤테이션 — 착수점 11-B절 가드(test_280cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 280
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '280cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
J = '작업지시서.md'
L = '근거_결정대기대장_20260915.md'
R = os.path.join('docs', 'work-orders', 'README.md')
M = [
 ("M1 WO 건수를 문서에서만 고침", J, "**14건 전부 종결**(완료 13 · 자료 대기 1). 대기 0.",
  "**14건 전부 종결**(완료 14 · 자료 대기 0). 대기 0."),
 ("M2 도달률을 문서에서만 고침", J, "기상 4표 도달 **68/172**(39.5%)", "기상 4표 도달 **80/172**(46.5%)"),
 ("M3 못 닿는 지역 수 틀림", J, "나머지 104지역은 **잇지 않고 주입**받는다", "나머지 92지역은 **잇지 않고 주입**받는다"),
 ("M4 평단가 커버리지 틀림", J, "평단가 개산은 249규격 중 18규격", "평단가 개산은 249규격 중 40규격"),
 ("M5 결정 대기 건수 틀림", J, "결정**(D-1~D-4 · D-14, 5건)", "결정**(D-1~D-4 · D-14, 4건)"),
 ("M6 자료 대기 하나를 뺌", J, "| **S-3** | 농진청 OPEX 코드 CSV(0바이트)", "| S-3 | 농진청 OPEX 코드 CSV(0바이트)"),
 ("M7 새 과제 하나를 뺌", J, "| **N-4** | **기재부 편성지침", "| N-4 | **기재부 편성지침"),
 ("M8 대응표가 있다고 바꿈", J, "공식 「시군구 → 관측지점」 대응표는 **없다**", "공식 대응표를 쓴다"),
 ("M9 「지어내지 않는다」 삭제", J, "나머지는 `None`이고 **지어내지 않는다**", "나머지는 근사값을 쓴다"),
 ("M10 기본설계 범위를 넓힘", J, "그래서 N-1은 **「구조 기본설계」까지**다", "그래서 N-1은 전 범위를 낸다"),
 ("M11 사용성 한계 삭제", J, "**사용자 인터뷰 0명 · 사용성 실측 0회**", "사용성을 확인했다"),
 ("M12 「읽혀 보지 않았다」 삭제", J, "**읽혀 보지 않았다**", "읽혀 보았다"),
 ("M13 11절 본문을 지움", J, "### P0 — 즉시", "### P0 — 지움"),
 ("M14 대장 대기 건수 틀림", L, "지금 대기 5건 · 닫힘 12건", "지금 대기 4건 · 닫힘 13건"),
 ("M15 WO 상태를 바꿈", R, "| 278차 | WO-011 | 완료 |", "| 278차 | WO-011 | 대기 |"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
