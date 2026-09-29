"""279차 뮤테이션 — 지침 요율 등재 가드(test_279cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 279
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '279cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
E = 'smartfarm_engine.py'
D = '근거_설계감리요율_원문대조_20260929.md'
L = '근거_결정대기대장_20260915.md'
C = 'consulting_package.py'
M = [
 ("M1 설계비 한 칸을 원문과 다르게", E, "(1_000_000_000, 6.16, 1.66, 1.70),", "(1_000_000_000, 6.15, 1.66, 1.70),"),
 ("M2 공사감리비 한 칸 틀림", E, "(3_000_000_000, 5.10, 1.48, 1.52),", "(3_000_000_000, 5.10, 1.49, 1.52),"),
 ("M3 사업관리비 한 칸 틀림", E, "(10_000_000_000, 4.15, 1.41, 1.32),", "(10_000_000_000, 4.15, 1.41, 1.30),"),
 ("M4 구간 상한을 바꿈", E, "(5_000_000_000, 4.67, 1.45, 1.42),", "(6_000_000_000, 4.67, 1.45, 1.42),"),
 ("M5 사이 값을 보간", E, "    row = next(r for r in GUIDELINE_FEE_RATE_TABLE if construction_cost_won <= r[0])",
  "    row = GUIDELINE_FEE_RATE_TABLE[0]"),
 ("M6 표 밖에서 값을 지어냄", E, '"사유": "지침 표는 100억원까지만 준다 — 그 밖의 값을 지어내지 않는다",',
  '"사유": "표 밖은 마지막 구간을 쓴다",'),
 ("M7 사업관리비 확인요망 제거", E, '"사업관리비_주의": "[확인요망] " + GUIDELINE_FEE_RATE_BASIS["mgmt_origin_chain"],',
  '"사업관리비_주의": GUIDELINE_FEE_RATE_BASIS["mgmt_origin_chain"],'),
 ("M8 사슬에서 미확보 표기 삭제", E, "기획재정부 편성지침의 시설부대경비 요율(원문 미확보)",
  "기획재정부 편성지침의 시설부대경비 요율"),
 ("M9 적용 사업을 지움", E, '"applies_to": "스마트팜 ICT 융복합확산(온실신축) 사업",',
  '"applies_to": "모든 사업",'),
 ("M10 건축사대가기준 구분 삭제", E, '"not_applies": "그 밖의 공공발주 건축공사 — 건축사대가기준 별표5(SUPERVISION_FEE_RATE_TABLE)",',
  '"not_applies": "",'),
 ("M11 근거 문서의 미확보 기록 삭제", D, "사업관리비는 원문을 **확보하지 못했다**", "사업관리비 원문도 확보했다"),
 ("M12 대장 닫힘 표기 되돌림", L, "~~**D-17**~~ ✅**닫힘(279차)**", "**D-17** ⏳**대기**"),
 ("M13 조립 계층에서 지침 요율 제거", C, '"지침 요율(온실신축)": e.guideline_fee_reference(',
  '"지침 요율(미사용)": e.design_supervision_fee_reference('),
 ("M14 확인하지 못한 것 삭제", D, "지침이 왜 감리만 비상주 계열을 골랐는지", "지침이 감리 계열을 고른 이유는 분명하다"),
 ("M15 비고 5 인용 삭제", D, "요율표가 작성되지 않은 다른 분야는 **도로분야의 요율을 적용**한다",
  "도로 열을 쓰기로 했다"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
