"""225차 뮤테이션 — 그 차수 가드를 일부러 깨서 잡히는지 잰다(265차에 작업 임시 폴더에서 리포로 옮김, 내용은 당시 그대로).
실행: python mutations/run_all.py 225  (원본 통과 확인·파일 복원은 실행기가 한다)
"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 리포 루트(265차 — 절대 경로 제거)
sys.stdout.reconfigure(encoding='utf-8')
T = 'webapp_templates/case_detail.html'
CP = 'consulting_package.py'
M = [
 ("M1 형식 문자열 변경", CP, '<일련 4>-<검증문자 1>"', '<일련 4>"'),
 ("M2 dict 통째 표시(배지)", CP, '"ksfid": num["ksfid"] if num else None,', '"ksfid": num if num else None,'),
 ("M3 dict 통째 표시(스테퍼)", CP, "f\"식별번호 {d25['식별번호']['ksfid']}\"", "f\"식별번호 {d25['식별번호']}\""),
 ("M4 배지에 등급 싣기", T, '<span class="il">추적 식별자 · K-SFID · 등급 아님</span>',
  '<span class="il">추적 식별자 · K-SFID · 등급 아님</span> 등급 {{ d25["등급"].grade }}'),
 ("M5 대기 슬롯 하드코딩", T, '{% for m in badge.missing %}<code>{{ m }}</code>{% if not loop.last %} · {% endif %}{% endfor %}',
  '<code>ksfid_seq</code>'),
 ("M6 만료일 누락", T, '{% if badge.expires %}<span class="ie">만료 {{ badge.expires }}</span>{% endif %}', ''),
 ("M7 발급 상태 무시", CP, '    return {"issued": bool(num),', '    return {"issued": False,'),
 ("M8 부록의 dict 표시", T, '<code>{{ d25["식별번호"].ksfid }}</code>', '<code>{{ d25["식별번호"] }}</code>'),
 ("M9 유효기간 dict 표시", CP, "f\"유효기간 {d25['유효기간']['issued']} ~ {d25['유효기간']['expires']}\"",
  "f\"유효기간 {d25['유효기간']}\""),
 ("M10 번호 하드코딩", T, '<code class="iv">{{ badge.ksfid }}</code>', '<code class="iv">KSF-2026</code>'),
]
res = []
for name, f, a, b in M:
    raw = open(f, 'rb').read()
    s = raw.decode('utf-8')
    if s.count(a) != 1:
        res.append((name, f"적용 불가({s.count(a)})")); continue
    open(f, 'wb').write(s.replace(a, b).encode('utf-8'))
    try:
        r = subprocess.run([sys.executable, '-m', 'pytest', 'test_webapp.py', '-q', '-k', '225cha or 224cha'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        res.append((name, "잡음" if r.returncode != 0 else "놓침"))
    finally:
        open(f, 'wb').write(raw)
for n, r in res: print(r, n)
