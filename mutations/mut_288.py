"""288차 뮤테이션 — 서비스 흐름 가드(test_288cha)를 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 288
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '288cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
W = 'webapp.py'
T = os.path.join('webapp_templates', 'service_flow.html')
B = os.path.join('webapp_templates', '_base.html')
M = [
 # ── 🔴 축을 새로 만듦 ───────────────────────────────────────────────
 ("M1 3대상에 없는 값을 끼움", C, 'FLOW_TARGETS: tuple = ("부지", "시설", "기자재")',
  'FLOW_TARGETS: tuple = ("부지", "시설", "기자재", "인력")'),
 ("M2 3대상 하나를 뺌", C, 'FLOW_TARGETS: tuple = ("부지", "시설", "기자재")',
  'FLOW_TARGETS: tuple = ("부지", "시설")'),
 ("M3 척추 순서를 뒤집음", C, '    for st in STAGE_ORDER:' + chr(10) + '        docs = []',
  '    for st in reversed(STAGE_ORDER):' + chr(10) + '        docs = []'),
 # ── 🔴 수를 다시 세지 않고 흘림 ─────────────────────────────────────
 ("M4 산출물 하나를 흘림", C, '            docs.append({', '            docs.append({} if sp["code"] == "D3" else {'),
 ("M5 엔진 호출수를 틀리게", C, '"engine_n": len(sp.get("engine") or []),', '"engine_n": len(sp.get("engine") or []) + 1,'),
 ("M6 대상 집계를 틀리게", C, '"targets": [(t, sum(1 for d in docs if t in d["targets"])) for t in FLOW_TARGETS],',
  '"targets": [(t, len(docs)) for t in FLOW_TARGETS],'),
 ("M7 열합계를 레일에서 가져옴", C,
  '"col_total": [sum(1 for sp in PACKAGE_SPEC if t in (sp.get("targets") or []))' + chr(10) +
  '                            for t in FLOW_TARGETS]}',
  '"col_total": [len(spine) for _t in FLOW_TARGETS]}'),
 # ── 🔴 기존 매핑을 바꿔 붙임 ────────────────────────────────────────
 ("M8 기능 매핑을 뒤집음", C, '"fn": (fn or [FLOW_NO_LINK, ""])[0],', '"fn": (fn or [FLOW_NO_LINK, ""])[1],'),
 ("M9 판정 부록 표시 삭제", C, '"appendix": sp["code"] in JUDGMENT_CODES,', '"appendix": False,'),
 ("M10 기입 단계를 임의로 붙임", C, '            steps = list(ENTRY_STEP_ALL_CODES) + list(',
  '            steps = list(ENTRY_STEP_ALL_CODES) + ["rules"] + list('),
 ("M11 플랫폼을 아무 데나 붙임", C, '        for st in stages:' + chr(10) + '            plat_of[st] = ',
  '        for st in STAGE_ORDER:' + chr(10) + '            plat_of[st] = '),
 # ── 🔴 렌즈가 없는 화면을 가리킴 ────────────────────────────────────
 ("M12 렌즈가 없는 경로를 가리킴", C, '("참조", "/refs", "리포가 쥔 자료', '("참조", "/references", "리포가 쥔 자료'),
 ("M13 렌즈 하나 삭제", C, '        ("관점", "/for", "농업인·투자자·공공기관 — 누가 읽는가"),' + chr(10), ''),
 # ── 🔴 공백을 지우거나 배정해 버림 ──────────────────────────────────
 ("M14 화면↔단계 공백 삭제", C, '{"무엇": "화면 ↔ 단계 대응", "왜": (', '{"무엇": "없음", "왜": ('),
 ("M15 「정의돼 있지 않다」 삭제", C, '**리포 어디에도 정의돼 있지 않다**', '아래와 같이 정한다'),
 ("M16 「판단이라 만들지 않는다」 삭제", C, '배정하는 것은 판단이라 이 함수가 만들지 않는다',
  '배정은 이 함수가 한다'),
 # ── 🔴 판정·순위 유입 ───────────────────────────────────────────────
 ("M17 화면에 판정 어휘", T, '<h2>렌즈 — 같은 산출물을 다르게 보는 축</h2>', '<h2>렌즈 — 권장 보기</h2>'),
 ("M18 매트릭스 경계 삭제", T, '<b>어느 칸이 더 낫다고 하지 않는다.</b>', '칸이 클수록 중요하다.'),
 ("M19 단계 경계 삭제", C, '어떤 단계도 더 중요하다고 하지 않는다', '④타당성검증이 가장 중요하다'),
 ("M20 「축을 새로 만들지 않았습니다」 삭제", T, '축을 새로 만들지 않았습니다', '새 축입니다'),
 # ── 🔴 메뉴·라우트 ──────────────────────────────────────────────────
 ("M21 머리 메뉴 링크 제거", B, '<a href="/flow">서비스 흐름<small>', '<a href="/flow_x">서비스 흐름<small>'),
 ("M22 푸터 링크 제거", B, '<a href="/flow">서비스 흐름</a>', '<a href="/flow_y">서비스 흐름</a>'),
 ("M23 라우트 경로 변경", W, '@app.get("/flow")', '@app.get("/flow2")'),
 ("M24 사용 안내에서 화면 삭제", C, '    ("/flow", "서비스 흐름", "척추인 6단계에',
  '    ("/flow_z", "서비스 흐름", "척추인 6단계에'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
