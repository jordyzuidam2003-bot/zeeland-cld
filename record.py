"""The record of the CLD's changes since the Research Proposal, read back from git.

    python3 record.py                   # each agreed change since the tag proposal, then each
                                        # difference no commit explains (exit 1 if there is one)
    python3 record.py --message FILE    # the same, FILE the message of the commit being made

Git is the only record of why the CLD differs from the version the Research Proposal shows (the tag
`proposal`): a commit that changes what model/cld.json or model/cld-texts.md says, layout aside,
ends its message in three lines,

    Change: <what it does>
    Argument: <a source, or the rule's conditions it meets>
    Agreed: Jordy and Lenne, <YYYY-MM-DD>

one change per commit. A commit made before this record existed gets its lines from a later
commit, whose message ends in one block per commit it explains, each after a line `Commit: <sha>`
(rejected: rewriting pushed history to add them). A block whose words a later check finds wrong
(an argument stronger than its source) is replaced the same way, after a line `Corrects: <sha>`,
its Agreed: the day Jordy agreed the correction; the record shows the latest correction in the
commit's place, since a later check can find a corrected block wrong too, and a message corrects a
commit at most once.

read() gives the agreed changes, oldest first (a block carried for an earlier commit in that
commit's place), from which build.py writes the report's appendix of changes
(docs/tables/cld-changes.tex), and the problems: each item (an element, link, named or combined
loop as changes.py names it, or a section of cld-texts.md) that differs between `proposal` and the
model on disk while some commit since changed it without a block, and each block that is malformed
or explains nothing. build.py --check stops on a problem, so the commit-msg hook refuses the commit
that brings one. The model on disk differing from HEAD is the commit being made, explained by
FILE's block; with no FILE it is not yet explained. Merges are skipped: their changes are their
branch's commits.
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import changes

ROOT = Path(__file__).resolve().parent
TAG = "proposal"
FILES = ("model/cld.json", "model/cld-texts.md")
KEYS = ("Change", "Argument", "Agreed")
LINE = re.compile(r"(Commit|Corrects|Change|Argument|Agreed): ?(.*)")
AGREED = re.compile(r"Jordy and Lenne, (\d{4}-\d{2}-\d{2})")
SCISSORS = "# ------------------------ >8 ------------------------"  # git commit -v: the diff below it
PENDING = "the commit being made"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def blocks(message):
    """[(sha named by Commit: or Corrects:, or None for the commit's own, {Change, Argument, Agreed,
    date, corrects})] of a message's closing blocks; ValueError where they are not as the module's
    docstring says.

    >>> blocks("Fix a typo")
    []
    >>> [(s, b["Change"], b["date"]) for s, b in blocks("Fold X\\n\\nChange: X folded\\nArgument: the rule\\nAgreed: Jordy and Lenne, 2026-11-20\\n")]
    [(None, 'X folded', datetime.date(2026, 11, 20))]
    >>> [s for s, _ in blocks("Lines\\n\\nCommit: 4da3bba\\nChange: a\\nArgument: b\\nAgreed: Jordy and Lenne, 2026-11-20\\nCommit: 7782c35\\nChange: c\\nArgument: d\\nAgreed: Jordy and Lenne, 2026-11-20")]
    ['4da3bba', '7782c35']
    >>> [(s, b["corrects"]) for s, b in blocks("Lines\\n\\nCorrects: 513adb3\\nChange: a\\nArgument: b\\nAgreed: Jordy and Lenne, 2026-11-21")]
    [('513adb3', True)]
    >>> blocks("Change: a\\nAgreed: Jordy and Lenne, 2026-11-20")
    Traceback (most recent call last):
    ...
    ValueError: a block needs Change:, Argument: and Agreed:, in that order, each in words
    >>> blocks("Change: a\\nArgument: b\\nAgreed: Jordy, 2026-11-20")
    Traceback (most recent call last):
    ...
    ValueError: Agreed: reads 'Jordy and Lenne, YYYY-MM-DD', not 'Jordy, 2026-11-20'
    >>> blocks("Change: a\\nArgument: b\\nAgreed: Jordy and Lenne, 2026-11-20\\n\\nMore text")
    Traceback (most recent call last):
    ...
    ValueError: the Change:, Argument: and Agreed: lines end the message
    """
    lines = []
    for line in message.split("\n"):
        if line.startswith(SCISSORS):
            break
        if not line.startswith("#"):  # git's comments, in a message from the editor
            lines.append(line.rstrip())
    first = next((i for i, line in enumerate(lines) if LINE.fullmatch(line)), None)
    if first is None:
        return []
    tail = [line for line in lines[first:] if line]
    if not all(LINE.fullmatch(line) for line in tail):
        raise ValueError("the Change:, Argument: and Agreed: lines end the message")
    out, i = [], 0
    while i < len(tail):
        sha, corrects = None, tail[i].startswith("Corrects:")
        if tail[i].startswith(("Commit:", "Corrects:")):
            sha = LINE.fullmatch(tail[i])[2].strip()
            i += 1
        group = [LINE.fullmatch(line) for line in tail[i:i + 3]]
        if [m[1] for m in group] != list(KEYS) or not all(m[2].strip() for m in group):
            raise ValueError("a block needs Change:, Argument: and Agreed:, in that order, each in words")
        block = {**{m[1]: m[2].strip() for m in group}, "corrects": corrects}
        m = AGREED.fullmatch(block["Agreed"])
        try:
            block["date"] = datetime.date.fromisoformat(m[1]) if m else None
        except ValueError:
            block["date"] = None
        if block["date"] is None:
            raise ValueError(f"Agreed: reads 'Jordy and Lenne, YYYY-MM-DD', not {block['Agreed']!r}")
        out.append((sha, block))
        i += 3
    if sum(sha is None for sha, _ in out) > 1:
        raise ValueError("one change per commit: a message holds one block of its own")
    return out


def snapshot(rev=None):
    """{item name: what it says} of the model at rev, or on disk: each element, link, named and
    combined loop without its layout (changes.content()), and each section of cld-texts.md, its
    comments left out as the page leaves them."""
    read = (lambda f: (ROOT / f).read_text()) if rev is None else (lambda f: git("show", f"{rev}:{f}"))
    items = {name: changes.content(item) for name, (_, item) in changes.items(json.loads(read(FILES[0]))).items()}
    texts = re.sub(r"<!--.*?-->\n?", "", read(FILES[1]), flags=re.S)
    parts = re.split(r"^## (.+)\n", texts, flags=re.M)
    items["model texts: the facts"] = parts[0].strip()
    items.update({f"model texts: {h}": body.strip() for h, body in zip(parts[1::2], parts[2::2])})
    return items


def differ(a, b):
    return {n for n in a.keys() | b.keys() if a.get(n) != b.get(n)}


def read(message=None):
    """([{change, argument, date}] oldest first, [problem, …]): the module's docstring."""
    problems = []
    log = git("log", "--reverse", "--no-merges", "--format=%H%x00%s%x00%B%x01", f"{TAG}..HEAD").split("\x01")
    commits = [c.strip("\n").split("\x00") for c in log if c.strip()]
    if message is not None:
        commits.append([PENDING, PENDING, message])
    subject = {sha: s for sha, s, _ in commits}
    short = lambda sha: sha if sha == PENDING else f"{sha[:7]} ({subject[sha][:60]})"
    own, carried, corrected = {}, {}, {}
    for sha, _, body in commits:
        try:
            found = blocks(body)
        except ValueError as e:
            problems.append(f"{short(sha)}: {e}")
            continue
        for target, block in found:
            if target is None:
                own[sha] = block
                continue
            full = next((c for c, _, _ in commits if c != PENDING and c.startswith(target)), None) if len(target) >= 7 else None
            word = "Corrects" if block["corrects"] else "Commit"
            if full is None:
                problems.append(f"{short(sha)}: {word}: {target} names no commit since the tag {TAG}")
            elif block["corrects"]:
                if corrected.get(full, (None,))[0] == sha:
                    problems.append(f"{short(sha)}: corrects {full[:7]} twice")
                else:
                    corrected[full] = (sha, block)  # commits run oldest first: the latest correction holds
            elif full in carried:
                problems.append(f"{short(sha)}: {full[:7]} has its block already")
            else:
                carried[full] = block

    # what each commit changes in what the model says; the files on disk differ from HEAD by the commit being made
    touching = git("rev-list", "--reverse", "--no-merges", f"{TAG}..HEAD", "--", *FILES).split()
    changed = {sha: differ(snapshot(f"{sha}^"), snapshot(sha)) for sha in touching}
    disk = snapshot()
    pending = differ(snapshot("HEAD"), disk)
    if pending:
        changed[PENDING] = pending

    for full, (by, _) in corrected.items():
        if full not in own and full not in carried:
            problems.append(f"{short(by)}: Corrects: {full[:7]}, which has no block to correct")

    rows = []
    for sha, _, _ in commits:
        mine = [b for b in (own.get(sha), carried.get(sha)) if b]
        if len(mine) > 1:
            problems.append(f"{short(sha)}: carries its own block and has one carried for it: one change, one block")
        if mine and not changed.get(sha):
            problems.append(f"{short(sha)}: its block explains nothing, since it changes nothing the model says")
        if mine and sha in corrected:
            mine = [corrected[sha][1]]
        rows += [{"change": b["Change"], "argument": b["Argument"], "date": b["date"]} for b in mine[:1]]

    explained = {sha for sha in changed if sha in own or sha in carried}
    for name in sorted(differ(snapshot(TAG), disk)):
        for sha in [s for s in changed if name in changed[s] and s not in explained]:
            if sha == PENDING:
                problems.append(f"{name}: changed since the last commit, and " + (
                    "the commit's message carries no Change:, Argument: and Agreed: lines" if message is not None
                    else "no commit explains it yet: commit it with its Change:, Argument: and Agreed: lines"))
            else:
                problems.append(f"{name}: differs from the tag {TAG}, changed in {short(sha)} with no Change:, "
                                f"Argument: and Agreed: lines; a later commit carries them as Commit: {sha[:7]}")
    return rows, problems


def main():
    args = sys.argv[1:]
    if args and not (len(args) == 2 and args[0] == "--message"):
        sys.exit(__doc__.split("\n\n")[1])
    message = Path(args[1]).read_text() if args else None
    rows, problems = read(message)
    print("# The CLD's changes since the Research Proposal\n")
    for n, r in enumerate(rows, 1):
        print(f"{n}. **{r['change']}** {r['argument']} Agreed by Jordy and Lenne, {r['date'].isoformat()}.")
    if problems:
        sys.exit("\n".join(problems))


if __name__ == "__main__":
    main()
