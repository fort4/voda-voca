# 2026-11-06 - voda-voca - 신규 400단어(시험 대비 200 + 실무 비즈니스 200) 검증·IPA 변환·시드 JSON·검수표 생성기 (일회성 도구)
# 파일 위치: ai-agent/claude/261106_카탈로그_400단어/build.py
#
# 사용:
#   python3 -I build.py <cmudict.dict> <seeds 디렉터리> --table <검수표.md>            # 검증과 검수표만 (시드를 쓰지 않음)
#   python3 -I build.py <cmudict.dict> <seeds 디렉터리> --table <검수표.md> --apply    # words/*.json 과 vocabularies.json 에 병합
#
# 데이터 출처: CMU Pronouncing Dictionary (Copyright (C) 1993-2015 Carnegie Mellon University, BSD 계열 라이선스).
# IPA 변환은 ai-agent/claude/작업계획_261106_IPA_변환.py 의 to_ipa() 를 재사용한다.

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ipa_tool", HERE.parent / "작업계획_261106_IPA_변환.py")
ipa_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ipa_tool)

ALLOWED_POS = {"noun", "verb", "adjective", "adverb", "preposition", "conjunction"}
HANGUL = re.compile(r"[가-힣]")

# 신규 단어장 메타 (결정 확정: level 3, sort_order 4·5, 시험 대비는 상표 대신 서술형 표기)
METAS = [
    {
        "slug": "exam-core-200",
        "title": "시험 대비 핵심 200",
        "category": "EXAM",
        "level": 3,
        "description": "영어 공인시험의 지문과 문제에 자주 나오는 비즈니스·일상 어휘",
        "sort_order": 4,
    },
    {
        "slug": "business-practical-200",
        "title": "실무 비즈니스 영단어 200",
        "category": "BUSINESS",
        "level": 3,
        "description": "회의·이메일·협상 등 직장에서 바로 쓰는 어휘",
        "sort_order": 5,
    },
]

# 수기 확정 IPA (CMUdict 미수록·품사별 강세가 갈리는 단어). 문자열은 IPA 직접 지정, 정수는 CMUdict 변형 번호(1부터).
OVERRIDES: dict[str, int | str] = {
    # 품사가 달라 강세가 갈리는 단어: 시드의 품사(명사/동사)에 맞춘다
    "refund": 2,  # noun ˈrifʌnd
    "discount": 2,  # noun ˈdɪskaʊnt
    "survey": "ˈsɝˌveɪ",  # noun
    "upgrade": "ˈʌpˌɡreɪd",  # noun
    "update": "ˈʌpˌdeɪt",  # noun
    "transfer": "trænsˈfɝ",  # verb (CMU 음절 경계 보정)
    "coordinate": 2,  # verb koʊˈɔrdəˌneɪt
    "elaborate": 2,  # verb ɪˈlæbəˌreɪt
    # 사전 발음이 여럿일 때 미국 사전에서 더 흔한 쪽
    "advertisement": 2,
    "inquiry": 1,
    "retire": "rɪˈtaɪɚ",
    "employee": 2,
    "employer": 2,
    "mentor": 2,
    "significant": 2,
    "surcharge": 2,  # noun ˈsɝtʃɑrdʒ
    "subordinate": 2,  # noun
    "affiliate": 2,  # noun
    "director": 4,
    "implement": "ˈɪmpləˌmɛnt",  # verb
    "oversee": "ˌoʊvɚˈsi",  # verb
    # 복합어: 1차 강세는 하나만 두고 나머지는 2차 강세로 내린다
    "attendee": "əˌtɛnˈdi",
    "overseas": "ˌoʊvɚˈsiz",
    "trainee": "ˌtreɪˈni",
}


def fix_syllables(ipa: str) -> str:
    """CMUdict 의 ER 은 'ər' 을 한 음소로 쓴다. 뒤에 모음이 이어지면 r 을 다음 음절로 돌려준다 (ɚˈeɪ → əˈreɪ, ɚɪ → ərɪ)."""
    vowels = "aeiouæɑɔɛɪʊʌəɝ"
    ipa = re.sub(rf"ɚ([ˈˌ])(?=[{vowels}])", r"ə\1r", ipa)
    return re.sub(rf"ɚ(?=[{vowels}])", "ər", ipa)


def forms(term: str) -> set[str]:
    """tests/test_system_seed.py 의 _forms 와 같은 규칙."""
    t = term.lower()
    f = {t, t + "s", t + "es", t + "d", t + "ed", t + "ing", t + "er", t + "ers", t + "ly", t + "'s"}
    if t.endswith("e"):
        f |= {t[:-1] + "ing", t[:-1] + "ed", t[:-1] + "er", t[:-1] + "ers", t + "r", t + "rs"}
    if t.endswith("y"):
        f |= {t[:-1] + "ies", t[:-1] + "ied", t[:-1] + "ier", t[:-1] + "ily"}
    if len(t) >= 2:
        f |= {t + t[-1] + "ed", t + t[-1] + "ing", t + t[-1] + "er", t + t[-1] + "ers"}
    return f


def parse(path: Path) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 5:
            raise SystemExit(f"{path.name}:{n}: 필드가 5개가 아닙니다 ({len(parts)})")
        term, pos, meaning, example, example_meaning = (p.strip() for p in parts)
        rows.append({"term": term, "pos": pos, "meaning": meaning, "example": example, "example_meaning": example_meaning, "_line": n})
    return rows


def validate(sets: dict[str, list[dict]], existing: set[str]) -> list[str]:
    problems: list[str] = []
    seen: dict[str, str] = {}
    for slug, rows in sets.items():
        meanings = Counter(r["meaning"] for r in rows)
        for r in rows:
            w, where = r["term"], f"{slug}:{r['_line']} {r['term']}"
            if not re.fullmatch(r"[a-z]+", w):
                problems.append(f"{where}: 표제어는 소문자 단일 단어여야 합니다")
            if r["pos"] not in ALLOWED_POS:
                problems.append(f"{where}: 품사 '{r['pos']}' 허용 밖")
            if w in existing:
                problems.append(f"{where}: 기존 600단어와 겹칩니다")
            if w in seen:
                problems.append(f"{where}: {seen[w]} 와 중복")
            seen[w] = slug
            tokens = set(re.findall(r"[a-z]+(?:'[a-z]+)?", r["example"].lower()))
            if not tokens & forms(w):
                problems.append(f"{where}: 예문에 표제어(또는 규칙 활용형)가 없습니다 → {r['example']}")
            if not HANGUL.search(r["meaning"]) or not HANGUL.search(r["example_meaning"]):
                problems.append(f"{where}: 뜻/예문 뜻에 한글이 없습니다")
            if HANGUL.search(r["example"]):
                problems.append(f"{where}: 영문 예문에 한글이 있습니다")
            if meanings[r["meaning"]] > 1:
                problems.append(f"{where}: 뜻 '{r['meaning']}' 이 단어장 안에서 중복")
            if len(r["meaning"]) > 200 or len(r["example"]) > 500 or len(r["example_meaning"]) > 500:
                problems.append(f"{where}: 길이 초과")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmudict", type=Path)
    ap.add_argument("seeds", type=Path)
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    sets = {m["slug"]: parse(HERE / f"{m['slug']}.src") for m in METAS}
    existing = {w["term"].lower() for f in (args.seeds / "words").glob("*.json") if f.stem not in sets for w in json.loads(f.read_text(encoding="utf-8"))}
    problems = validate(sets, existing)
    for slug, rows in sets.items():
        if len(rows) != 200:
            problems.append(f"{slug}: 단어 {len(rows)}개 (200개여야 합니다)")

    cmu = ipa_tool.load_cmudict(args.cmudict)
    out: dict[str, list[dict]] = {}
    table = []
    heteronyms = []
    for slug, rows in sets.items():
        meta = next(m for m in METAS if m["slug"] == slug)
        table.append(f"\n## {meta['title']} (`{slug}`, {len(rows)}단어)\n")
        table.append("| # | 단어 | IPA | 품사 | 뜻 | 예문 | 비고 |\n| ---: | :--- | :--- | :--- | :--- | :--- | :--- |")
        out[slug] = []
        for i, r in enumerate(rows, 1):
            key = r["term"]
            variants = cmu.get(key, [])
            if key in OVERRIDES:
                value = OVERRIDES[key]
                ipa = value if isinstance(value, str) else fix_syllables(ipa_tool.to_ipa(variants[value - 1]))
                note = "수기 지정" + ("" if isinstance(value, str) else f" (CMU 변형 {value}번)")
            elif variants:
                ipa = fix_syllables(ipa_tool.to_ipa(variants[0]))
                note = f"CMU 변형 {len(variants)}개 중 1번" if len(variants) > 1 else ""
                if len(variants) > 1:
                    heteronyms.append((slug, key, [ipa_tool.to_ipa(v) for v in variants]))
            else:
                problems.append(f"{slug}: '{key}' CMUdict 미수록, OVERRIDES 필요")
                continue
            if not re.fullmatch(r"[a-zæðŋθɐ-˿̀-ͯ ]+", ipa) or len(ipa) > 100:
                problems.append(f"{slug}: '{key}' IPA '{ipa}' 가 시드 규칙을 어김")
            if ipa.count("ˈ") > 1:
                problems.append(f"{slug}: '{key}' IPA '{ipa}' 1차 강세가 2개 이상")
            out[slug].append({"term": key, "phonetic": ipa, "pos": r["pos"], "meaning": r["meaning"], "example": r["example"], "example_meaning": r["example_meaning"]})
            table.append(f"| {i} | {key} | /{ipa}/ | {r['pos']} | {r['meaning']} | {r['example']} | {note} |")

    header = (
        "# 검토 — 신규 400단어 검수표 (v2.2 카탈로그 확충, 이슈 #24)\n\n"
        "- 생성: 2026-11-06, `ai-agent/claude/261106_카탈로그_400단어/build.py`\n"
        "- 구성: 시험 대비 핵심 200(`exam-core-200`, EXAM) + 실무 비즈니스 영단어 200(`business-practical-200`, BUSINESS), 모두 단일 단어, level 3\n"
        "- IPA 출처: CMU Pronouncing Dictionary (Copyright (C) 1993-2015 Carnegie Mellon University, BSD 계열 라이선스)를 미국식 IPA 로 변환. 슬래시는 화면 표기이며 DB 에는 슬래시 없이 저장\n"
        "- 강세: ˈ 1차, ˌ 2차. 단음절 단어는 강세 표시 생략\n"
        "- 비고의 `수기 지정`은 CMUdict 값이 품사·뜻에 맞지 않아 직접 확정한 값, `CMU 변형 N개 중 1번`은 사전에 발음이 여럿이라 첫 번째를 쓴 값이므로 **특히 확인**해 주세요\n"
    )
    args.table.write_text(header + "\n".join(table) + "\n", encoding="utf-8")

    print(f"단어 {sum(len(v) for v in out.values())}개, 문제 {len(problems)}건, 발음 변형이 여럿인 단어 {len(heteronyms)}개")
    for p in problems:
        print("  -", p)
    if "--list-heteronyms" in sys.argv or heteronyms:
        for slug, term, ipas in heteronyms:
            print(f"  [변형] {term}: {' | '.join(ipas)}")
    if problems:
        return 1
    if args.apply:
        vocab_path = args.seeds / "vocabularies.json"
        metas = json.loads(vocab_path.read_text(encoding="utf-8"))
        have = {m["slug"] for m in metas}
        metas += [m for m in METAS if m["slug"] not in have]
        vocab_path.write_text(json.dumps(metas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for slug, words in out.items():
            (args.seeds / "words" / f"{slug}.json").write_text(json.dumps(words, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("시드 JSON 병합 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
