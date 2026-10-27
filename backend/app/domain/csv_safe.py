"""Spreadsheet formula-injection protection for CSV export."""
import csv, io

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v  # real numbers are written as-is (a negative number is not a formula)
    s = str(v)
    return "'" + s if s.startswith(_DANGEROUS) else s


def to_csv(rows, columns) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for r in rows:
        w.writerow([safe_cell(r.get(c)) for c in columns])
    return buf.getvalue()
