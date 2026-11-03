# 2026-11-02 - voda-voca - GitHub 이슈 등록 스크립트: 이슈 초안 문서를 읽어 gh CLI 로 이슈와 라벨을 만든다 (기본은 드라이런)
# 파일 위치: ai-agent/claude/작업계획_261102_GitHub이슈_등록.py
"""사용법
    python3 ai-agent/claude/작업계획_261102_GitHub이슈_등록.py            # 드라이런: 등록될 내용만 출력
    python3 ai-agent/claude/작업계획_261102_GitHub이슈_등록.py --apply    # 실제 등록 (gh auth login 이 끝나 있어야 함)
"""

import re
import subprocess
import sys
from pathlib import Path

DRAFT = Path(__file__).with_name("작업계획_261102_GitHub이슈_초안.md")
LABEL_COLORS = {"enhancement": "a2eeef", "priority:high": "d73a4a", "priority:medium": "fbca04", "priority:low": "0e8a16"}


def parse_issues(text: str) -> list[dict]:
    """'## N. [기능] 제목' 블록을 이슈로 읽는다. 라벨은 '- **라벨**:' 줄, 본문은 '**본문**' 아래 '---' 전까지."""
    issues = []
    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        header, _, rest = block.partition("\n")
        title_match = re.match(r"\d+\.\s*(?:\[[^\]]+\]\s*)?(.+)", header.strip())
        if not title_match:
            continue
        label_line = re.search(r"^- \*\*라벨\*\*:\s*(.+)$", rest, flags=re.MULTILINE)
        labels = [part.strip() for part in label_line.group(1).split(",")] if label_line else []
        body_match = re.search(r"\*\*본문\*\*\s*\n(.*?)(?=^---\s*$|\Z)", rest, flags=re.MULTILINE | re.DOTALL)
        body = body_match.group(1).strip() if body_match else ""
        issues.append({"title": title_match.group(1).strip(), "labels": labels, "body": body})
    return issues


def run(cmd: list[str], apply: bool) -> None:
    print("$ " + " ".join(cmd[:4]) + " ...")
    if apply:
        subprocess.run(cmd, check=False)


def main() -> None:
    apply = "--apply" in sys.argv
    issues = parse_issues(DRAFT.read_text(encoding="utf-8"))
    print(f"이슈 {len(issues)}건 파싱됨 (apply={apply})")
    labels = sorted({label for issue in issues for label in issue["labels"]})
    for label in labels:
        color = LABEL_COLORS.get(label, "ededed")
        run(["gh", "label", "create", label, "--color", color, "--force"], apply)
    for issue in issues:
        print(f"- {issue['title']}  [{', '.join(issue['labels'])}]")
        cmd = ["gh", "issue", "create", "--title", issue["title"], "--body", issue["body"]]
        for label in issue["labels"]:
            cmd += ["--label", label]
        run(cmd, apply)


if __name__ == "__main__":
    main()
