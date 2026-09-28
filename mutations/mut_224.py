"""224차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 224  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
T = 'webapp_templates/entry_hub.html'
CP = 'consulting_package.py'
M = [
 ("M1 문서 칸을 완료로", CP, '(("경로 없음", "미제출 "', '(("완료", "미제출 "'),
 ("M2 발급 칸을 대기로 위장", CP, 'else ("경로 없음", "ksfid_seq 미주입', 'else ("대기", "ksfid_seq 미주입'),
 ("M3 근거 대조 status 목록 축소", CP, 'ENTRY_OPEN_PROVENANCE: tuple = ("추정", "확인요망", "미검증")',
  'ENTRY_OPEN_PROVENANCE: tuple = ("추정", "확인요망")'),
 ("M4 템플릿 상태 하드코딩", T, '<span class="chip {{ step_cls.get(s.state, \'chip-ref\') }}">{{ s.state }}</span>',
  '<span class="chip {{ step_cls.get(s.state, \'chip-ref\') }}">완료</span>'),
 ("M5 단계 하나 누락", T, '{% for s in r.steps %}', '{% for s in r.steps[:6] %}'),
 ("M6 단계 순서 뒤바꿈", CP, '    ("issue", "발급", "사람", "認定証発行(인증서 발행)"),\n    ("renew", "연차 재검", "사람", "年次審査(연차심사)"),',
  '    ("renew", "연차 재검", "사람", "年次審査(연차심사)"),\n    ("issue", "발급", "사람", "認定証発行(인증서 발행)"),'),
 ("M7 등급 문구 하드코딩", CP, 'f"등급 {g.get(\'grade\')} · 통과', 'f"등급 C · 통과'),
 ("M8 발급 상태 주입 무시", CP, '(("완료", f"식별번호 {d25[\'식별번호\']}") if d25.get("식별번호")',
  '(("완료", f"식별번호 {d25[\'식별번호\']}") if False'),
 ("M9 엔진 단계를 사람으로", CP, '("engine", "엔진 검증", "엔진",', '("engine", "엔진 검증", "사람",'),
 ("M10 템플릿 산술", T, '{{ s.detail }}', '{{ s.detail }}{{ loop.index - 1 }}'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-x', '-k', '224cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
