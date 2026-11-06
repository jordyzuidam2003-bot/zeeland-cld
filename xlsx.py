"""Write a spreadsheet as an .xlsx file with the standard library alone, so the repository needs
nothing installed (README, Setup).

    xlsx.workbook([(name, widths, rows), ...]) -> bytes

Each sheet: its name, each column's width in characters, and its rows, the first a header, in
bold and frozen; a cell is a string (a newline breaks its line) or a number, every cell wrapped and
aligned to the top. The bytes depend only on the sheets: the zip's entries are stored, not
compressed, with one fixed date, so build.py --check can compare the file byte for byte.
"""

import io
import zipfile
from xml.sax.saxutils import escape

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
# style 0 the default; 1 bold, wrapped, top; 2 wrapped, top
STYLES = (XML + f'<styleSheet xmlns="{MAIN}">'
          '<fonts count="2"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><name val="Arial"/></font></fonts>'
          '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
          '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
          '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs>'
          '</styleSheet>')


def column(i):
    """The column letter of index i: 0 A, 25 Z, 26 AA."""
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


def workbook(sheets):
    strings, index = [], {}

    def shared(text):
        if text not in index:
            index[text] = len(strings)
            strings.append(text)
        return index[text]

    parts = {}
    for n, (name, widths, rows) in enumerate(sheets, 1):
        cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths))
        body = []
        for r, row in enumerate(rows, 1):
            style = 1 if r == 1 else 2
            cells = []
            for c, value in enumerate(row):
                ref = f"{column(c)}{r}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
                elif value not in ("", None):
                    cells.append(f'<c r="{ref}" s="{style}" t="s"><v>{shared(str(value))}</v></c>')
            body.append(f'<row r="{r}">{"".join(cells)}</row>')
        parts[f"xl/worksheets/sheet{n}.xml"] = (
            XML + f'<worksheet xmlns="{MAIN}"><sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{cols}</cols><sheetData>{"".join(body)}</sheetData></worksheet>')
    parts["xl/sharedStrings.xml"] = (XML + f'<sst xmlns="{MAIN}" count="{len(strings)}" uniqueCount="{len(strings)}">'
                                     + "".join(f'<si><t xml:space="preserve">{escape(s)}</t></si>' for s in strings) + "</sst>")
    parts["xl/styles.xml"] = STYLES
    names = [s[0] for s in sheets]
    parts["xl/workbook.xml"] = (XML + f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>'
                                + "".join(f'<sheet name="{escape(nm)}" sheetId="{n}" r:id="rId{n}"/>' for n, nm in enumerate(names, 1))
                                + "</sheets></workbook>")
    k = len(names)
    parts["xl/_rels/workbook.xml.rels"] = (
        XML + f'<Relationships xmlns="{PKG}">'
        + "".join(f'<Relationship Id="rId{n}" Type="{REL}/worksheet" Target="worksheets/sheet{n}.xml"/>' for n in range(1, k + 1))
        + f'<Relationship Id="rId{k + 1}" Type="{REL}/styles" Target="styles.xml"/>'
        + f'<Relationship Id="rId{k + 2}" Type="{REL}/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
    parts["_rels/.rels"] = (XML + f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" '
                            f'Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    ct = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    parts["[Content_Types].xml"] = (
        XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="{ct}.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{n}.xml" ContentType="{ct}.worksheet+xml"/>' for n in range(1, k + 1))
        + f'<Override PartName="/xl/styles.xml" ContentType="{ct}.styles+xml"/>'
        f'<Override PartName="/xl/sharedStrings.xml" ContentType="{ct}.sharedStrings+xml"/></Types>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for name in ["[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                     "xl/styles.xml", "xl/sharedStrings.xml", *(f"xl/worksheets/sheet{n}.xml" for n in range(1, k + 1))]:
            z.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), parts[name])
    return buf.getvalue()
