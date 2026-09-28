"""hwpx 본문 텍스트 추출 (269차 신설).

왜 따로 두는가 — `chunking_lib_v2`의 `hwp_extract_text`는 **OLE2 .hwp** 전용이고,
농식품부가 게시하는 사업시행지침은 **zip 기반 .hwpx**다. 214차·269차가 지침 원문을
열 때 쓴 경로를 재현 가능하게 남긴다.

🔴 269차 교훈 — **표를 두 번 세지 않는다.** 첫 추출은 문단(`hp:p`) 하나를 잡고 그
아래 모든 `hp:t`를 모았는데, 표는 문단 안에 들어가고 **표의 칸도 다시 문단**이라
표 안 글자가 바깥 문단과 칸 문단에 **두 번** 잡혔다. 그 상태로 센 2025년 지침은
「위탁설계 24 · 자가설계 43」이었고, 조상 문단 기준으로 고치자 **17 · 28**이 되어
214차 실측과 **일치**했다 — 재현이 파서 결함을 잡은 것이다.
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET

SECTION = re.compile(r"Contents/section\d+\.xml$")


def _local(el):
    return el.tag.split("}")[-1]


def hwpx_text(path):
    """hwpx 본문을 문단 단위 텍스트로 낸다.

    각 `hp:t`는 **가장 가까운 조상 문단** 하나에만 귀속시킨다. 표 안 문단이
    바깥 문단에 겹쳐 잡히는 것을 막는 유일한 지점이다.
    """
    z = zipfile.ZipFile(path)
    lines = []
    for name in sorted(n for n in z.namelist() if SECTION.match(n)):
        root = ET.fromstring(z.read(name))
        owner = {}

        def walk(el, cur):
            if _local(el) == "p":
                cur = el
            if _local(el) == "t":
                owner[el] = cur
            for child in el:
                walk(child, cur)

        walk(root, None)
        buf, order = {}, []
        for el in root.iter():
            if _local(el) == "t" and el in owner:
                p = owner[el]
                if p not in buf:
                    buf[p] = []
                    order.append(p)
                if el.text:
                    buf[p].append(el.text)
        lines.extend("".join(buf[p]) for p in order)
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.buffer.write(hwpx_text(sys.argv[1]).encode("utf-8"))
