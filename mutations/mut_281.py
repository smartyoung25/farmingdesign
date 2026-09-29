"""281차 뮤테이션 — 기본설계 입구 가드(test_281cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 281
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '281cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
C = 'consulting_package.py'
W = 'webapp.py'
T = os.path.join('webapp_templates', 'basic_design.html')
B = os.path.join('webapp_templates', '_base.html')
M = [
 ("M1 기상 미도달을 조용히 넘김", C, '        cannot.append({"무엇": "기상값(설계외기온·난방도일·풍속·일조)", "왜": (',
  '        pass if True else cannot.append({"무엇": "기상값(설계외기온·난방도일·풍속·일조)", "왜": ('),
 ("M2 평단가 None을 0으로 채움", C, '            v = e.greenhouse_total_estimate(s["이름"], py)',
  '            v = e.greenhouse_total_estimate(s["이름"], py) or 0'),
 ("M3 평단가 미등재 사유 삭제", C,
  '            if v is None:' + chr(10) + '                missing.append',
  '            if False:' + chr(10) + '                missing.append'),
 ("M4 「고르지 않는다」 경계 삭제", C, "🔴 **고르지 않는다.**", "규격을 골라 준다."),
 ("M5 최소사양 주의 삭제", C, '"주의": "최소사양은 **참고**다 — 어느 규격이 낫다고 하지 않는다",',
  '"주의": "이 규격을 쓰면 된다",'),
 ("M6 통과 규격수를 틀리게", C, '"통과_규격수": len(withc["candidates"]),', '"통과_규격수": len(base["candidates"]),'),
 ("M7 특화형 없음을 숨김", C, '"이 작목의 **특화형 규격이 등록돼 있지 않다** — 일반형만 본다"',
  '"이 작목 규격으로 골랐다"'),
 ("M8 난방부하 한계 삭제", C, '    cannot.append({"무엇": "난방부하·연료량", "왜": (',
  '    [] if True else cannot.append({"무엇": "난방부하·연료량", "왜": ('),
 ("M9 작기 한계 삭제", C, '    cannot.append({"무엇": "적정작기·작형", "왜": (',
  '    [] if True else cannot.append({"무엇": "적정작기·작형", "왜": ('),
 ("M10 작목 판정 금지 삭제", C, '    cannot.append({"무엇": "작목 적합 판정", "왜": (',
  '    [] if True else cannot.append({"무엇": "작목 적합 판정", "왜": ('),
 ("M11 「구조 기본설계까지」 삭제", C, "이 입구는 **「구조 기본설계」까지**다", "이 입구가 전부 낸다"),
 ("M12 빈칸 경고 삭제", C, "빈칸으로 두면 «없는 것»이 «0»으로 읽힌다", "빈칸으로 두면 된다"),
 ("M13 잘못된 면적을 200으로", W, '        raise HTTPException(status_code=400, detail=f"면적은 숫자여야 한다: {area_m2!r}")',
  '        area = None'),
 ("M14 화면에서 「낼 수 없는 것」 절 제거", T, '<h2>이 입구가 <b>낼 수 없는 것</b></h2>', '<h2>참고</h2>'),
 ("M16 조립 계층에 뺄셈 유입", C, 'crop_note = ("일반형 %d · 이 작목 포함 %d"',
  'crop_note = ("일반형 %d · 특화형 %d" % (len(base["candidates"]), len(withc["candidates"]) - len(base["candidates"])) or "일반형 %d · 이 작목 포함 %d"'),
 ("M15 메뉴 링크 제거", B, '<a href="/design">기본설계<small>', '<a href="/design_x">기본설계<small>'),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
