"""뮤테이션 실행기 — 차수별 가드를 일부러 깨서 잡히는지 다시 잰다(265차).

  python mutations/run_all.py            # 전부(오래 걸린다 — 스크립트마다 pytest를 여러 번 돈다)
  python mutations/run_all.py 262 263    # 지정한 차수만

한 스크립트마다:
  ① **원본 통과 확인** — 스크립트가 부르는 테스트 파일과 `-k` 선택자를 모아 먼저 돌린다. 실패하면 그 스크립트의
     「잡음」은 무효라 돌리지 않는다(254차 교훈: 원본이 실패한 채 5/5가 나왔다).
  ② **안전 복원** — 스크립트가 이름으로 부르는 리포 파일을 실행 전에 바이트 그대로 저장하고, 끝나면(시간 초과·중단 포함)
     달라진 것을 되돌린다. 스크립트 안의 try/finally 위에 한 겹 더 둔다.
  ③ **집계** — 출력 줄의 「잡음」·「놓침」·「적용불가」를 센다. 「적용불가」는 그 뒤 코드가 바뀌어 옛 패턴이 없어진 것이라
     **실패가 아니라 낡음**으로 따로 보고한다(스크립트는 당시 기록이라 고치지 않는다).
종료 코드: 원본 실패·놓침·스크립트 오류가 하나라도 있으면 1.
"""
import glob, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')

# 265차 재현에서 나온 놓침 가운데 **가드 결함이 아닌 것** — 분류와 이유를 함께 둔다.
#   여기 없는 놓침은 새 결함이라 실패로 친다. 가드 결함(무뎌짐)은 여기 올리지 않고 가드를 고친다
#   (265차: 228·234차 레지스트리 기록 단언이 뒤 차수 서술의 같은 차수 번호에 무뎌져 있었다 → 조임).
KNOWN = {
    '233': {'M3 굽은 따옴표 추측 치환': '등가 변이 — 234~236차에 따옴표 변형 별칭이 전부 등재돼 추측 치환과 결과가 같다'},
    '234': {'M2 따옴표 일괄 치환': '등가 변이 — 235·236차에 변형 전부 등재',
            'M4 ‘ 별칭도 추가': '등가 변이 — 235차에 ‘가 사용자 지시로 등재됐다'},
    '235': {'M2 백틱 일괄 치환': '등가 변이 — 236차에 백틱 등재',
            'M4 백틱 별칭 추가': '등가 변이 — 236차에 백틱이 사용자 지시로 등재됐다'},
    '237': {'M1 v1.1 라우트 수 틀림': '대상 이동 — v1.1은 257차에 239차 동결 기록이 됐고 같은 검사는 v1.2에 한다',
            'M2 v1.1 보증 한계 문구 삭제': '대상 이동 — 〃',
            'M6 v1.1 레지스트리 수 낡음': '대상 이동 — 〃'},
    '238': {'M8 v1.1 ★ 글자 수로 복귀': '대상 이동 — 〃',
            'M9 v1.1 확인요망 과소': '대상 이동 — 〃',
            'M10 v1.1 KB 낡음': '대상 이동 — 〃'},
    '240': {'M5 지역명 부분 매칭이 생김(대장 미갱신)': '상태 변화 — D-5가 241차에 닫혀 가드의 「D-5 대기」 분기가 돌지 않는다'},
    '249': {'M1 D-11 WO의 D 번호 제거': '상태 변화 — D-11이 255차에 닫혀 열린 항목 검사 대상이 아니다',
            'M4 D-7 WO 중복': '상태 변화 — D-7이 250차에 닫혔다'},
}


def baseline_args(src):
    files = sorted(set(re.findall(r"'(test_\w+\.py)'", src))) or ['test_engine.py', 'test_webapp.py']
    ks = re.findall(r"'-k',\s*'([^']+)'", src)
    ks += [x for x in re.findall(r"'([^'\n]*\b\d{2,3}cha\b[^'\n]*)'", src) if x not in ks]
    return files, ks


def touched(src):
    """스크립트가 이름으로 부르는 리포 파일 — 문자열 리터럴과 os.path.join('a', 'b', …)."""
    names = set(re.findall(r"'([^'\n]+\.(?:py|md|html|json|txt))'", src))
    for m in re.finditer(r"os\.path\.join\(((?:\s*'[^']+'\s*,?)+)\)", src):
        names.add(os.path.join(*re.findall(r"'([^']+)'", m.group(1))))
    return sorted(n for n in names if os.path.isfile(n))


def num_of(path):
    return re.search(r'mut_(\d+)\.py', path).group(1)


def run_one(path):
    src = open(path, encoding='utf-8').read()
    files, ks = baseline_args(src)
    if ks:
        expr = ' or '.join(f'({k})' for k in ks)
        b = subprocess.run([sys.executable, '-m', 'pytest', *files, '-q', '-x', '-p', 'no:cacheprovider', '-k', expr],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
        if b.returncode != 0:
            return {'baseline': False, 'caught': 0, 'missed': 0, 'stale': 0, 'error': ''}
    keep = {n: open(n, 'rb').read() for n in touched(src)}
    res = {'baseline': True, 'caught': 0, 'missed': 0, 'stale': 0, 'error': '', 'restored': [], 'missed_names': []}
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', env=ENV, timeout=1800)
        for ln in r.stdout.splitlines():
            ln = ln.strip()
            if ln.startswith('잡음'):
                res['caught'] += 1
            elif ln.startswith('놓침'):
                name = ln[len('놓침'):].strip()
                if name in KNOWN.get(num_of(path), {}):
                    res['known'] = res.get('known', 0) + 1
                else:
                    res['missed'] += 1; res['missed_names'].append(ln)
            elif ln.startswith('적용불가'):
                res['stale'] += 1
        if r.returncode != 0:
            res['error'] = (r.stderr.strip().splitlines() or ['?'])[-1][:160]
    except subprocess.TimeoutExpired:
        res['error'] = '시간 초과'
    finally:
        for n, data in keep.items():
            if not os.path.exists(n) or open(n, 'rb').read() != data:
                open(n, 'wb').write(data)
                res['restored'].append(n)
    return res


def main(argv):
    want = set(argv)
    paths = sorted(glob.glob(os.path.join(ROOT, 'mutations', 'mut_*.py')))
    paths = [p for p in paths if not want or re.search(r'mut_(\d+)\.py', p).group(1) in want]
    bad = False
    print('차수 | 원본 | 잡음 | 놓침 | 알려진 놓침(분류) | 적용불가(낡음) | 비고')
    for p in paths:
        num = re.search(r'mut_(\d+)\.py', p).group(1)
        t0 = time.time()
        r = run_one(p)
        note = ' · '.join(x for x in (r['error'],
                                      '; '.join(r.get('missed_names', [])),
                                      ('복원: ' + ', '.join(r.get('restored', []))) if r.get('restored') else '') if x)
        print(f"{num} | {'통과' if r['baseline'] else '🔴실패(무효)'} | {r['caught']} | {r['missed']} | {r.get('known', 0)} | {r['stale']} | "
              f"{note} ({time.time() - t0:.0f}s)", flush=True)
        bad |= (not r['baseline']) or r['missed'] > 0 or bool(r['error'])
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
