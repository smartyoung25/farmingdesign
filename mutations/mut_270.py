"""270차 뮤테이션 — ICT 표준 목록 가드(test_270cha)를 일부러 깨서 잡히는지 잰다.
실행: python mutations/run_all.py 270
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트
sys.stdout.reconfigure(encoding='utf-8')
run = lambda: subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', '-q', '-x', '-k', '270cha'],
                             capture_output=True).returncode
assert run() == 0, "원본이 실패한다 — 뮤테이션 무효"
D = '근거_외부수집_기능공백_20260924.md'
C = 'consulting_package.py'
M = [
 ("M1 집계표만 고침(행은 그대로)", D, "| KS(국가표준) | **23** |", "| KS(국가표준) | **24** |"),
 ("M2 전수표에서 한 행 삭제", D, "| TTAS | 55 |", "| TTAS_X | 55 |"),
 ("M3 게시물 합 틀림", D, "| **게시물 합** | **68** |", "| **게시물 합** | **69** |"),
 ("M4 모집단 경고 삭제", D, "**이것은 「스마트팜 ICT 표준의 전체 목록」이 아니다.**", "이것이 전체 목록이다."),
 ("M5 기사 시점 지움", D, "**네 해 전 수치**", "지금 수치"),
 ("M6 두 수를 같은 자로 잼", D, "말은 **하지 않는다**", "말은 **할 수 있다**"),
 ("M7 3268·3269를 있다고 단정", D, "**[미확인]으로 남긴다.**", "3268·3269는 제정됐다."),
 ("M8 게시판에 없다는 사실 삭제", D, "**KOAT 게시판 55건에 KS X 3268·3269는 없다**", "게시판에 전부 있다"),
 ("M9 G2를 2차로 되돌림", C, '"found": "1차", "where": ("농진원(KOAT)', '"found": "2차", "where": ("농진원(KOAT)'),
 ("M10 blocked에서 미확인 번호 삭제", C, "⚠️KS X 3268·3269는 보도자료엔", "⚠️KS X 3265는 보도자료엔"),
 ("M11 건수를 조립 계층에 적음", C, '"why": "표준 번호 체계를 엔진이 모른다', '"why": "표준 55건 — 표준 번호 체계를 엔진이 모른다'),
 ("M12 403 재확인 기록 삭제", D, "HTTP 403 동일", "이번엔 열렸다"),
 ("M13 미확인 목록 축소", D, "표준 **본문**은 하나도 열지 않았다", "표준 본문까지 전부 읽었다"),
 ("M14 D-3 관찰 결론 뒤집음", D, "**고칠 것이 없다**", "**고쳐야 한다**"),
]
for n, f, a, b in M:
    raw = open(f, 'rb').read(); s = raw.decode('utf-8')
    if s.count(a) < 1: print("적용 불가", n); continue
    open(f, 'wb').write(s.replace(a, b, 1).encode('utf-8'))
    try: print("잡음" if run() else "놓침", n)
    finally: open(f, 'wb').write(raw)
assert run() == 0
