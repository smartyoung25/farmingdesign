"""269차 뮤테이션 — 2026년 지침 확보 가드(test_269cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 269
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '269cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_외부수집_기능공백_20260924.md'
E = 'smartfarm_engine.py'
C = 'consulting_package.py'
H = 'hwpx_extract.py'
L = '근거_결정대기대장_20260915.md'
M = [
 ("M1 기준사업비 0회를 1회로", D, "| 기준사업비 | **0** | **0** | **0** |", "| 기준사업비 | **1** | **0** | **0** |"),
 ("M2 미주입의 뜻을 흐림", D, "채워야 할 구멍이 아니라 정확한 상태", "채워야 할 구멍으로 남아 있는 상태"),
 ("M3 주입 경로 폐기 서술", D, "그래도 **주입 경로는 그대로 둔다**", "그래서 **주입 경로는 없앤다**"),
 ("M4 D5 미주입 키 제거", C, '"미주입": "기준사업비(standard_cost_won)', '"주입됨": "기준사업비(standard_cost_won)'),
 ("M5 요율을 엔진 코드에 등재", E, "SUPERVISION_FEE_GRADES = (", "GUIDELINE_FEE_RATES = (6.16, 5.47, 5.1, 4.67, 4.15)\nSUPERVISION_FEE_GRADES = ("),
 ("M6 D-17 대기 표시 삭제", E, "**결정 대기 D-17**이고 엔진이 고를 일이 아니다", "엔진이 알아서 고른다"),
 ("M7 ★2022-104 준거 불변 문장 삭제", D, "221차 ★결정(2022-104호 준거)이 **최신 지침에서도 그대로 서 있다**", "준거는 다시 정해야 한다"),
 ("M8 내재해형이 가점이라고 뒤집음", D, "🔴 **내재해형은 이 목록에 없다**", "🔴 **내재해형이 이 목록에 있다**"),
 ("M9 파서 검산 기준 삭제", D, "**214차 측정이 오늘의 검산 기준이 됐다.**", "검산 기준은 없었다."),
 ("M10 조상 문단 귀속 제거", H, "owner[el] = cur", "owner[el] = el"),
 ("M11 D-17 대장에서 삭제", L, "| **D-17** ⏳**대기** |", "| D-17 대기 |"),
 ("M12 미대조 범위 문구 삭제", D, "전문을 줄 단위로 2025년판과 대조하지 않았다", "전문을 줄 단위로 2025년판과 대조했다"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
