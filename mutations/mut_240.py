"""240차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 240  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
L = '근거_결정대기대장_20260915.md'
M = [
 ("M1 정리표에서 D-9 행 누락", L, '| D-9 | 「동절기」 개월 정의', '| (삭제) | 「동절기」 개월 정의'),
 ("M2 정리표 행을 굵게(겹침 유발)", L, '| D-12 | 품셈 공종 선언 순서 재정렬', '| **D-12** | 품셈 공종 선언 순서 재정렬'),
 ("M3 제목 대기 수 낡음", L, '~~13건~~ 대기 15건', '~~13건~~ 대기 13건'),
 ("M4 D-5 영향 서술 삭제", L, '**C1·C3에서 3칸이 비어 있다**', '**영향 없음**'),
 ("M5 지역명 부분 매칭이 생김(대장 미갱신)", 'consulting_package.py', '"난방 설계외기온": e.design_outdoor_temp(region),', '"난방 설계외기온": e.design_outdoor_temp(region.split("(")[-1].rstrip(")") if "(" in region else region),'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_engine.py', 'test_webapp.py', '-q', '-x',
                            '-k', '240cha or 207cha or 216cha or 153cha or 149cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
