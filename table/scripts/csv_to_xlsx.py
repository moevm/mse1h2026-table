from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook


def _detect_dialect(csv_path: Path, encoding: str = "utf-8-sig") -> csv.Dialect:
    sample = csv_path.read_text(encoding=encoding, errors="replace")[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
    except csv.Error:
        return csv.get_dialect("excel")


def csv_to_xlsx(
    csv_path: str | Path,
    xlsx_path: str | Path | None = None,
    sheet_name: str = "Sheet1",
    encoding: str = "utf-8-sig",
) -> str:
    csv_path = Path(csv_path).resolve()

    if xlsx_path is None:
        xlsx_path = csv_path.with_suffix(".xlsx")
    else:
        xlsx_path = Path(xlsx_path).resolve()

    xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    dialect = _detect_dialect(csv_path, encoding=encoding)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]

    with csv_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.reader(f, dialect=dialect)
        for row in reader:
            ws.append(row)

    wb.save(xlsx_path)
    return str(xlsx_path)