# 2026-11-06 - voda-voca - 표준 단어 600개 IPA 생성기: CMUdict(미국식 ARPAbet) → IPA 변환, 검수표 생성, 시드 JSON 병합 (일회성 도구)
# 파일 위치: ai-agent/claude/작업계획_261106_IPA_변환.py
#
# 사용:
#   python3 -I 작업계획_261106_IPA_변환.py <cmudict.dict> <seeds 디렉터리> --table <검수표.md>
#   python3 -I 작업계획_261106_IPA_변환.py <cmudict.dict> <seeds 디렉터리> --table <검수표.md> --apply
# --apply 가 없으면 시드 파일을 건드리지 않는다.
#
# 데이터 출처: CMU Pronouncing Dictionary (Copyright (C) 1993-2015 Carnegie Mellon University, BSD 계열 라이선스).

import argparse
import collections
import json
import re
import sys
from pathlib import Path

# ARPAbet → IPA (미국식). 모음의 0/1/2 는 강세 번호다.
VOWELS = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɝ", "EY": "eɪ",
    "IH": "ɪ", "IY": "i", "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
}
CONSONANTS = {
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k", "L": "l", "M": "m",
    "N": "n", "NG": "ŋ", "P": "p", "R": "r", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j",
    "Z": "z", "ZH": "ʒ",
}

# 영어에서 단어 첫머리에 올 수 있는 자음 군(최대 onset). 음절 경계를 정할 때 쓴다.
_LEGAL_ONSETS = {
    # 두 자음
    *[a + b for a in "pbtdkgfvθ" for b in "lr" if (a + b) not in ("tl", "dl")],
    "kw", "gw", "tw", "dw", "θw", "ʃr", "sl", "sw", "sp", "st", "sk", "sm", "sn", "sf", "hj", "mj", "nj", "pj", "bj", "tj", "dj",
    "kj", "fj", "vj", "sj", "lj", "zj", "θj",
    # 세 자음
    "spl", "spr", "str", "skr", "skw", "skl", "spj", "stj", "skj",
}

# 수기 확정 (뜻·품사·관용에 맞춘 값). 정수는 CMUdict 변형 번호(1부터), 문자열은 IPA 직접 지정.
OVERRIDES: dict[str, int | str] = {
    "and": 2,  # 약형(ənd)이 아닌 완전형
    "close": 2,  # 시드 뜻 '닫다'(동사) → /kloʊz/
    "decade": 2,  # ˈdɛkeɪd
    "advocate": 2,  # 시드 뜻 '옹호하다, 옹호자' 중 첫 뜻(동사)
    "obsolete": 2,  # 주강세가 마지막 음절
    "read": 2,  # 시드 뜻 '읽다' 원형 /rid/
    "sometimes": 2,
    "direction": "dəˈrɛkʃən",
    "embrace": "ɪmˈbreɪs",
    "encourage": "ɪnˈkɝɪdʒ",
    "every": "ˈɛvri",
    "genuine": "ˈdʒɛnjuɪn",
    "increase": "ɪnˈkris",  # 시드 뜻 '증가하다'(동사)
    "inside": "ɪnˈsaɪd",
    "replace": "rɪˈpleɪs",
    "require": "rɪˈkwaɪɚ",
    "research": "ˈriˌsɝtʃ",  # 시드 뜻 '연구, 조사'(명사)
    "adversity": "ædˈvɝsəti",
    # CMUdict 의 ER 이 "ər" 을 뜻하는데 모음 앞이라 ɚ 로 나오는 단어: 음절 경계를 바로잡는다 (forever, encourage 는 원래 표기가 맞다)
    "different": "ˈdɪfərənt",
    "arrange": "əˈreɪndʒ",
    "arrive": "əˈraɪv",
    "career": "kəˈrɪr",
    "generous": "ˈdʒɛnərəs",
    "memory": "ˈmɛməri",
    "operate": "ˈɑpəˌreɪt",
    "original": "əˈrɪdʒənəl",
    "ameliorate": "əˈmiljəˌreɪt",
    "deliberate": "dɪˈlɪbərət",
    "derive": "dɪˈraɪv",
    "ephemeral": "ɪˈfɛmərəl",
    "exonerate": "ɪɡˈzɑnəˌreɪt",
    "rhetoric": "ˈrɛtərɪk",
    "sporadic": "spəˈrædɪk",
    "without": "wɪðˈaʊt",
    "outside": "ˌaʊtˈsaɪd",  # CMU 는 1차 강세가 둘
    "sagacious": "səˈɡeɪʃəs",  # CMUdict 미수록
}
# 품사에 따라 발음이 달라지는 14개 후보 (검수표에서 따로 표시)
HETERONYM_CANDIDATES = {
    "advocate", "close", "deliberate", "finance", "frequent", "house", "increase", "minute", "object", "permit",
    "progress", "read", "refuse", "research",
}


def load_cmudict(path: Path) -> dict[str, list[list[str]]]:
    entries: dict[str, list[list[str]]] = collections.defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        word, *phones = line.split()
        entries[re.sub(r"\(\d+\)$", "", word)].append(phones)
    return entries


def to_ipa(phones: list[str]) -> str:
    """ARPAbet 음소열 → IPA. 강세는 음절의 onset 앞에 ˈ(1차) / ˌ(2차)로 둔다. 단음절 단어는 강세 표시를 생략한다."""
    # 1) 음소를 (IPA, 모음 여부, 강세) 로 바꾼다
    items: list[tuple[str, bool, str]] = []
    for ph in phones:
        m = re.fullmatch(r"([A-Z]+)([012])?", ph)
        if not m:
            raise ValueError(f"알 수 없는 음소: {ph}")
        base, stress = m.group(1), m.group(2) or ""
        if base in VOWELS:
            ipa = VOWELS[base]
            if base == "AH" and stress == "0":
                ipa = "ə"
            elif base == "ER" and stress == "0":
                ipa = "ɚ"
            items.append((ipa, True, stress))
        elif base in CONSONANTS:
            items.append((CONSONANTS[base], False, ""))
        else:
            raise ValueError(f"알 수 없는 음소: {ph}")

    vowel_positions = [i for i, (_, is_v, _) in enumerate(items) if is_v]
    syllable_count = len(vowel_positions)

    # 2) 각 모음 앞의 자음 중 '최대 onset' 만 그 음절에 붙인다 (나머지는 앞 음절의 coda)
    onset_start: dict[int, int] = {}
    prev_vowel = -1
    for vi in vowel_positions:
        consonants = list(range(prev_vowel + 1, vi))
        if prev_vowel == -1:
            start = consonants[0] if consonants else vi  # 단어 첫머리: 전부 onset
        else:
            start = vi
            for k in range(len(consonants)):  # 가장 긴 합법 onset 을 찾는다 (긴 것부터)
                cluster = "".join(items[c][0] for c in consonants[k:])
                if len(consonants) - k == 1 or cluster in _LEGAL_ONSETS or _all_legal(cluster):
                    start = consonants[k]
                    break
        onset_start[vi] = start
        prev_vowel = vi

    # 3) 강세 표시 삽입
    marks: dict[int, str] = {}
    if syllable_count > 1:
        for vi in vowel_positions:
            stress = items[vi][2]
            if stress == "1":
                marks[onset_start[vi]] = "ˈ"
            elif stress == "2":
                marks[onset_start[vi]] = "ˌ"
    # 2차 강세(ˌ)가 1차 강세(ˈ) 음절 바로 옆에 있으면 뺀다 (강세 충돌: 사전 표기 관례). 예: ˌɪnˈsɪst → ɪnˈsɪst
    order = [onset_start[vi] for vi in vowel_positions]  # 음절 순서대로 onset 위치
    for n, pos in enumerate(order):
        if marks.get(pos) != "ˌ":
            continue
        neighbours = [order[m] for m in (n - 1, n + 1) if 0 <= m < len(order)]
        if any(marks.get(q) == "ˈ" for q in neighbours):
            del marks[pos]
    out = []
    for i, (ipa, _, _) in enumerate(items):
        if i in marks:
            out.append(marks[i])
        out.append(ipa)
    return "".join(out)


def _all_legal(cluster: str) -> bool:
    """영어 첫머리에 올 수 있는 자음 군인지 (2·3자음 표에서 확인)."""
    return cluster in _LEGAL_ONSETS


def choose(term: str, variants: list[list[str]]) -> tuple[str, str]:
    """(IPA, 비고). 기본은 CMUdict 첫 변형, OVERRIDES 에 있으면 그 값."""
    note = f"변형 {len(variants)}개" if len(variants) > 1 else ""
    if term in OVERRIDES:
        value = OVERRIDES[term]
        if isinstance(value, str):
            return value, "수기 지정" + (f" (CMU 변형 {len(variants)}개)" if variants else " (CMU 미수록)")
        return to_ipa(variants[value - 1]), f"수기: CMU 변형 {value}번 선택 (총 {len(variants)}개)"
    return to_ipa(variants[0]), note


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmudict", type=Path)
    parser.add_argument("seeds", type=Path)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    cmu = load_cmudict(args.cmudict)
    metas = json.loads((args.seeds / "vocabularies.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    rows: list[str] = []
    results: dict[str, dict[str, str]] = {}
    for meta in metas:
        slug = meta["slug"]
        path = args.seeds / "words" / f"{slug}.json"
        words = json.loads(path.read_text(encoding="utf-8"))
        results[slug] = {}
        rows.append(f"\n## {meta['title']} (`{slug}`, {len(words)}단어)\n")
        rows.append("| # | 단어 | IPA | 뜻 | 비고 |\n| ---: | :--- | :--- | :--- | :--- |")
        for index, word in enumerate(words, 1):
            term = word["term"]
            key = term.lower()
            variants = cmu.get(key, [])
            if not variants and key not in OVERRIDES:
                problems.append(f"{slug}: '{term}' CMUdict 미수록, 수기 지정 필요")
                rows.append(f"| {index} | {term} | **(없음)** | {word['meaning']} | CMU 미수록 |")
                continue
            ipa, note = choose(key, variants)
            if key in HETERONYM_CANDIDATES:
                note = (note + "; " if note else "") + "품사별 발음 후보"
            results[slug][term] = ipa
            rows.append(f"| {index} | {term} | /{ipa}/ | {word['meaning']} | {note} |")

    header = (
        "# 검토 — 표준 단어 600개 IPA 검수표 (v2.2 발음기호)\n\n"
        "- 생성: 2026-11-06, `ai-agent/claude/작업계획_261106_IPA_변환.py`\n"
        "- 출처: CMU Pronouncing Dictionary (Copyright (C) 1993-2015 Carnegie Mellon University, BSD 계열 라이선스)를 미국식 IPA 로 변환\n"
        "- 규칙: CMUdict 첫 변형을 기본으로 사용, 뜻·품사·관용에 맞지 않는 단어는 수기 지정(비고에 표시). 슬래시는 화면 표기이며 DB 에는 슬래시 없이 저장\n"
        "- 강세: ˈ 1차, ˌ 2차. 단음절 단어는 강세 표시 생략. 장음 기호(ː)는 쓰지 않음(미국식 사전 표기 관례)\n"
    )
    args.table.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")

    # 문자 검증: 시드 로더 규칙과 같은 허용 문자
    allowed = re.compile(r"^[a-zæðŋθɐ-˿̀-ͯ ]+$")
    for slug, mapping in results.items():
        for term, ipa in mapping.items():
            if not allowed.fullmatch(ipa) or len(ipa) > 100:
                problems.append(f"{slug}: '{term}' IPA '{ipa}' 가 시드 규칙을 어김")
    total = sum(len(m) for m in results.values())
    print(f"변환 {total}개, 문제 {len(problems)}건")
    for problem in problems:
        print("  -", problem)
    if problems:
        return 1

    if args.apply:
        for meta in metas:
            slug = meta["slug"]
            path = args.seeds / "words" / f"{slug}.json"
            words = json.loads(path.read_text(encoding="utf-8"))
            merged = []
            for word in words:
                item: dict[str, str | None] = {}
                for key, value in word.items():
                    item[key] = value
                    if key == "term":
                        item["phonetic"] = results[slug][word["term"]]
                merged.append(item)
            path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("시드 JSON 에 phonetic 병합 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
