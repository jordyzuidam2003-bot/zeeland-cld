"""The report's tables as LaTeX rows, for the group's Overleaf project.

Imported by build.py, which writes docs/tables/<name>.tex. rows(header, rows) gives a file of rows
alone, `cell & cell \\\\` a line: the report holds each table's environment, caption, column
widths and header, and `\\input`s the rows, so the group shapes the table and the model fills it.
text(s, keys, cites) gives a model text as LaTeX: special characters escaped, *italics* as
\\emph, and each in-text citation of one of keys, as the model writes it (Kim, 2000, p. 16), as
biblatex-apa's \\parencite, \\textcite or \\cite with its locator, keyed as cld.json keys it,
the keys the group's Zotero items carry in Extra. A citation it cannot key raises ValueError.

    >>> cites = {"kim-2000": ("Kim", "2000", ""), "kaandorp-2022": ("Kaandorp et al.", "2022", "")}
    >>> text("the *Fixes that fail* archetype (Kim, 2000, p. 16).", ["kim-2000"], cites)
    'the \\\\emph{Fixes that fail} archetype \\\\parencite[p.~16]{kim-2000}.'
    >>> text("Kaandorp et al. (2022, pp. 24–25) show 15 m & more", ["kaandorp-2022"], cites)
    '\\\\textcite[pp.~24--25]{kaandorp-2022} show 15 m \\\\& more'
    >>> text("(B7; Kim, 2000, section 2)", ["kim-2000"], cites)
    '(B7; \\\\cite[section 2]{kim-2000})'
    >>> text("(Kim, 2000; Kaandorp et al., 2022, p. 3) and *Saline seepage (kwel)*", list(cites), cites)
    '\\\\parencites{kim-2000}[p.~3]{kaandorp-2022} and \\\\emph{Saline seepage (kwel)}'
    >>> text("The sign is the product (+, then −)")
    'The sign is the product (+, then $-$)'
    >>> text("No sources (R2, a hypothesis)")
    'No sources (R2, a hypothesis)'
    >>> text("as (Kim, 2001) says", ["kim-2000"], cites)
    Traceback (most recent call last):
    ...
    ValueError: a citation no source of the item matches: (Kim, 2001)
"""

import re

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "→": r"$\rightarrow$",
           "−": "$-$"}  # pdflatex's utf8 reads no U+2212
YEAR = r"(?:1[89]\d\d|20\d\d)[a-z]?|n\.d\.(?:-[a-z])?"


def escape(s):
    return "".join(SPECIAL.get(ch, ch) for ch in s)


def locator(s):
    """A locator as LaTeX: a tie after p. and pp., a range's en dash as --."""
    return re.sub(r"\b(pp?\.) ", r"\1~", escape(s.strip())).replace("–", "--")


def cite(command, key, loc):
    return f"\\{command}[{locator(loc)}]{{{key}}}" if loc else f"\\{command}{{{key}}}"


def text(s, keys=(), cites=None):
    """s as LaTeX, its citations of keys as biblatex-apa commands (the module's docstring). Each
    citation first becomes a placeholder, so *italics* round a parenthesis, as in *Saline seepage
    (kwel)*, stay one span when the rest is escaped."""
    names = {(cites[k][0], cites[k][1]): k for k in keys}
    done = []

    def hold(latex):
        done.append(latex)
        return f"\0{len(done) - 1}\0"

    def replace(m):
        if m.groupdict().get("narr"):
            if (m["narr"], m["ny"]) not in names:
                raise ValueError(f"a citation no source of the item matches: {m[0]}")
            return hold(cite("textcite", names[m["narr"], m["ny"]], m["nloc"]))
        parts = m["par"].split("; ")
        found = [citation(p, names) for p in parts]
        if all(found):
            return hold(cite("parencite", *found[0]) if len(found) == 1
                        else "\\parencites" + "".join(cite("", k, loc)[1:] for k, loc in found))
        if not any(found) and re.search(rf", (?:{YEAR})\b", m["par"]):
            raise ValueError(f"a citation no source of the item matches: ({m['par']})")
        return "(" + "; ".join(hold(cite("cite", *f)) if f else p for p, f in zip(parts, found)) + ")"

    # narrative citations, Name (year[, locator]), and parentheses, each in turn from the left
    authors = "|".join(sorted({re.escape(n) for n, _ in names}, key=len, reverse=True))
    pattern = re.compile((rf"(?P<narr>{authors}) \((?P<ny>{YEAR})(?:, (?P<nloc>[^()]*))?\)|" if names else "")
                         + r"\((?P<par>[^()]*)\)")
    return re.sub("\0(\\d+)\0", lambda m: done[int(m[1])], emph(pattern.sub(replace, s)))


def citation(part, names):
    """(key, locator) when part is Name, year[, locator] of one of names, else None."""
    for (n, y), k in names.items():
        m = re.fullmatch(rf"{re.escape(n)}, {re.escape(y)}(?:, (.+))?", part)
        if m:
            return k, m[1]
    return None


def emph(s):
    """Plain text as LaTeX, *italics* as \\emph."""
    return re.sub(r"\*(.+?)\*", r"\\emph{\1}", escape(s))


def rows(header, rows):
    """A file of rows, `cell & cell \\\\` each, under a comment naming its columns and its origin."""
    head = (f"% Written by ZeelandCLD's build.py from its model: edit the model there, never this file.\n"
            f"% Columns: {', '.join(header)}\n")
    return head + "".join(" & ".join(r) + " \\\\\n" for r in rows)
