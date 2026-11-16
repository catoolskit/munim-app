"""Write a report to an Excel file (or CSV if the Excel library is unavailable)."""
import csv, os


def write_table(path, title, headers, rows):
    """rows: lists of cells; use real numbers for amounts so Excel can add them up. Returns the path written."""
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        path = os.path.splitext(path)[0] + ".csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([title]); w.writerow([]); w.writerow(headers); w.writerows(rows)
        return path
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (title or "Report")[:31]
    ws.append([title]); ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.append([])
    ws.append(list(headers))
    for c in ws[3]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append(list(r))
    for i, h in enumerate(headers, 1):
        width = max([len(str(h))] + [len(f"{r[i - 1]:,.2f}" if isinstance(r[i - 1], float) else str(r[i - 1]))
                                       for r in rows if i - 1 < len(r)])
        ws.column_dimensions[ws.cell(row=3, column=i).column_letter].width = min(max(width + 2, 10), 50)
    for row in ws.iter_rows(min_row=4):
        for c in row:
            if isinstance(c.value, float):
                c.number_format = "#,##0.00"
    wb.save(path)
    return path
