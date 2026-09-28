"""273차 뮤테이션 — 콘솔 점검 가드(test_273cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 273
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '273cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_콘솔점검_20260929.md'
B = os.path.join('webapp_templates', '_base.html')
C = 'consulting_package.py'
R = os.path.join('docs', 'work-orders', 'README.md')
M = [
 ("M1 축 개수만 문서에서 고침", D, "`ENTRY_STEPS` | **7**", "`ENTRY_STEPS` | **8**"),
 ("M2 산출물 배정 수 틀림", D, "**F1 5 · F2 5 · F3 8 · F0 9**", "**F1 5 · F2 5 · F3 9 · F0 8**"),
 ("M3 참조 링크에 설명 추가(문서는 그대로)", B,
  '<a href="/pages/SmartFarm_벤치마크비교.html">벤치마크</a>',
  '<a href="/pages/SmartFarm_벤치마크비교.html">벤치마크<small>밴드</small></a>'),
 ("M4 드롭다운 F0 제외를 지움", B, "{% if f.fn != 'F0' %}", "{% if true %}"),
 ("M5 새 축을 만듦", C, "PLATFORM_STAGES: tuple = (", "OBJECT_AXIS = ('부지', '시설', '장비')\nPLATFORM_STAGES: tuple = ("),
 ("M6 다섯 번째 축 경고 삭제", D, "지금 새로 만들면 다섯 번째 축이 된다", "지금 만들면 된다"),
 ("M7 기입=매뉴얼로 뒤집음", D, "매뉴얼이 아니라 상태기계", "매뉴얼 그 자체"),
 ("M8 상태기계 보존 경고 삭제", D, "매뉴얼로 바꾸면 안 된다", "매뉴얼로 바꾸면 된다"),
 ("M9 축 연결 없음을 있다고 바꿈", D, "축이 넷이고, 이어 주는 화면이 없다", "축이 넷이고 전부 이어져 있다"),
 ("M10 WO 하나를 색인에서 뺌", R, "| [WO-013](WO-013_사용자매뉴얼_FAQ.md) |", "| WO-013 |"),
 ("M11 점검 문서 8절에서 WO 뺌", D, "| **WO-012** |", "| WO-012 |"),
 ("M12 사용성 실측 한계 삭제", D, "**사용성 실측을 하지 않았다**", "사용성 실측을 했다"),
 ("M13 사용자 0명 기록 삭제", D, "**사용자 수는 0명이다**", "사용자 인터뷰를 했다"),
 ("M14 근거 문서 시점 표기 삭제", D, "점검 시점 76건", "언제나 76건"),
 ("M15 참조 7중 2 결론 뒤집음", D, "**7 중 2.**", "**7 중 7.**"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
