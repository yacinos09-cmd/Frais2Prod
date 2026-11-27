"""
Génération des rapports PDF avec ReportLab (aucune dépendance externe lourde).

- ``generate_expense_pdf`` : détail de la répartition d'un frais de production.
- ``generate_global_pdf``  : gains consolidés par intervenant.
"""
from __future__ import annotations

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from utils import APP_DISPLAY_NAME, format_date, format_money, format_rate

ACCENT = colors.HexColor("#4338CA")
ACCENT_LIGHT = colors.HexColor("#EEF2FF")
DARK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#E2E8F0")
ZEBRA = colors.HexColor("#F8FAFC")
DANGER = colors.HexColor("#DC2626")
SUCCESS = colors.HexColor("#15803D")
WARNING = colors.HexColor("#B45309")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def _esc(text) -> str:
    return (str(text or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName="Helvetica",
                          fontSize=9.5, leading=13, textColor=DARK)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10, textColor=MUTED),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold",
                                fontSize=17, leading=21, spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=10.5, leading=14,
                                   textColor=MUTED),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=12,
                             leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=5),
        "cell": ParagraphStyle("cell", parent=base, fontSize=9, leading=11.5),
        "cell_b": ParagraphStyle("cell_b", parent=base, fontSize=9, leading=11.5,
                                 fontName="Helvetica-Bold"),
        "cell_r": ParagraphStyle("cell_r", parent=base, fontSize=9, leading=11.5,
                                 alignment=TA_RIGHT),
        "cell_rb": ParagraphStyle("cell_rb", parent=base, fontSize=9, leading=11.5,
                                  alignment=TA_RIGHT, fontName="Helvetica-Bold"),
        "head": ParagraphStyle("head", parent=base, fontSize=8.5, leading=11,
                               fontName="Helvetica-Bold", textColor=colors.white),
        "head_r": ParagraphStyle("head_r", parent=base, fontSize=8.5, leading=11,
                                 fontName="Helvetica-Bold", textColor=colors.white,
                                 alignment=TA_RIGHT),
    }


class _NumberedCanvas(rl_canvas.Canvas):
    """Canvas ajoutant en-tête/pied de page avec « Page X / Y »."""

    company = ""
    doc_title = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total: int):
        self.saveState()
        # Bandeau supérieur
        self.setFillColor(ACCENT)
        self.rect(0, PAGE_H - 6 * mm, PAGE_W, 6 * mm, stroke=0, fill=1)
        # Pied de page
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.6)
        self.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED)
        self.drawString(MARGIN, 9 * mm,
                        f"{self.company} — {self.doc_title}")
        self.drawRightString(PAGE_W - MARGIN, 9 * mm,
                             f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
                             f"  ·  Page {self._pageNumber} / {total}")
        self.restoreState()


def _canvas_factory(company: str, title: str):
    class _C(_NumberedCanvas):
        pass
    _C.company = company
    _C.doc_title = title
    return _C


def _header_block(st, company: str, address: str, title: str, subtitle_lines: list[str]):
    left = [Paragraph(_esc(company), ParagraphStyle(
        "co", parent=st["base"], fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT))]
    if address:
        left.append(Paragraph(_esc(address).replace("\n", "<br/>"), st["small"]))
    right = [Paragraph(datetime.now().strftime("%d/%m/%Y"),
                       ParagraphStyle("dt", parent=st["small"], alignment=TA_RIGHT))]
    top = Table([[left, right]], colWidths=[(PAGE_W - 2 * MARGIN) * 0.7,
                                             (PAGE_W - 2 * MARGIN) * 0.3])
    top.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow = [top, Spacer(1, 7 * mm), Paragraph(_esc(title), st["title"])]
    for line in subtitle_lines:
        flow.append(Paragraph(line, st["subtitle"]))
    flow.append(Spacer(1, 5 * mm))
    return flow


def _data_table(rows, col_widths, numeric_cols=(), total_row=False):
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
    ]
    last_body = len(rows) - (2 if total_row else 1)
    for i in range(1, last_body + 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    if total_row:
        style += [
            ("BACKGROUND", (0, -1), (-1, -1), ACCENT_LIGHT),
            ("LINEABOVE", (0, -1), (-1, -1), 1, ACCENT),
        ]
    t.setStyle(TableStyle(style))
    return t


def _summary_box(st, items: list[tuple[str, str, colors.Color]]):
    """Encadré de chiffres clés : [(libellé, valeur, couleur)]."""
    width = PAGE_W - 2 * MARGIN
    cells = []
    for label, value, color in items:
        cells.append([
            Paragraph(_esc(label).upper(), ParagraphStyle(
                "kl", parent=st["small"], fontSize=7, leading=9)),
            Paragraph(value, ParagraphStyle(
                "kv", parent=st["base"], fontName="Helvetica-Bold", fontSize=12.5,
                leading=16, textColor=color)),
        ])
    t = Table([cells], colWidths=[width / len(items)] * len(items))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _build(path: str, flow: list, company: str, title: str) -> str:
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm, bottomMargin=20 * mm,
        title=title, author=company, creator=APP_DISPLAY_NAME,
    )
    doc.build(flow, canvasmaker=_canvas_factory(company, title))
    return path


# --------------------------------------------------------------------------- #
# PDF 1 — Répartition d'un frais de production
# --------------------------------------------------------------------------- #

def generate_expense_pdf(path: str, expense: dict, allocations: list[dict],
                         company: str, address: str, currency: str) -> str:
    st = _styles()
    money = lambda v: format_money(v, currency)  # noqa: E731
    title = f"Répartition du frais : {expense['label']}"

    subtitle = [
        f"Projet : <b>{_esc(expense.get('project_name'))}</b>"
        + (f" &nbsp;·&nbsp; Client : <b>{_esc(expense.get('project_client'))}</b>"
           if expense.get("project_client") else ""),
        "Catégorie : " + _esc(expense.get("category") or "—")
        + (f" &nbsp;·&nbsp; Date : {format_date(expense.get('date'))}" if expense.get("date") else ""),
    ]
    flow = _header_block(st, company, address, title, subtitle)

    remaining = round(expense["amount"] - expense["allocated"], 2)
    rem_color = DANGER if remaining < -0.005 else (SUCCESS if abs(remaining) < 0.005 else WARNING)
    flow.append(_summary_box(st, [
        ("Montant total du frais", money(expense["amount"]), DARK),
        ("Total réparti", money(expense["allocated"]), ACCENT),
        ("Solde restant", money(remaining), rem_color),
    ]))
    flow.append(Spacer(1, 4 * mm))

    # Facture client associée
    if expense.get("invoice_reference"):
        inv_txt = (f"Facture client associée : <b>{_esc(expense['invoice_reference'])}</b>"
                   f" — {money(expense.get('invoice_amount') or 0)}"
                   + (f" encaissée le {format_date(expense.get('invoice_date'))}"
                      if expense.get("invoice_date") else ""))
    else:
        inv_txt = "Facture client associée : <i>aucune</i>"
    flow.append(Paragraph(inv_txt, st["base"]))
    if expense.get("notes"):
        flow.append(Paragraph("Note : " + _esc(expense["notes"]), st["small"]))

    flow.append(Paragraph("Détail de la répartition", st["h2"]))
    width = PAGE_W - 2 * MARGIN
    rows = [[Paragraph("Intervenant", st["head"]), Paragraph("Métier", st["head"]),
             Paragraph("Barème appliqué", st["head"]), Paragraph("Part", st["head_r"]),
             Paragraph("Montant dû", st["head_r"])]]
    for a in allocations:
        share = (a["amount"] / expense["amount"] * 100) if expense["amount"] else 0
        rows.append([
            Paragraph(_esc(a["worker_name"]), st["cell_b"]),
            Paragraph(_esc(a.get("role") or "—"), st["cell"]),
            Paragraph(_esc(format_rate(a["rate_type"], a["rate_value"], currency)), st["cell"]),
            Paragraph(f"{share:.1f}".replace(".", ",") + " %", st["cell_r"]),
            Paragraph(money(a["amount"]), st["cell_rb"]),
        ])
    if not allocations:
        rows.append([Paragraph("<i>Aucune répartition enregistrée.</i>", st["cell"]),
                     "", "", "", ""])
    rows.append([Paragraph("Sous-total réparti", st["cell_b"]), "", "", "",
                 Paragraph(money(expense["allocated"]), st["cell_rb"])])
    rows.append([Paragraph("Solde restant", st["cell_b"]), "", "", "",
                 Paragraph(f'<font color="{rem_color.hexval()}">{money(remaining)}</font>',
                           st["cell_rb"])])
    t = _data_table(rows, [width * 0.27, width * 0.2, width * 0.23, width * 0.1, width * 0.2])
    n = len(rows)
    t.setStyle(TableStyle([
        ("SPAN", (0, n - 2), (3, n - 2)),
        ("SPAN", (0, n - 1), (3, n - 1)),
        ("BACKGROUND", (0, n - 2), (-1, n - 1), ACCENT_LIGHT),
        ("LINEABOVE", (0, n - 2), (-1, n - 2), 1, ACCENT),
    ]))
    flow.append(t)

    if remaining < -0.005:
        flow.append(Spacer(1, 3 * mm))
        flow.append(Paragraph(
            f'<font color="{DANGER.hexval()}"><b>Attention :</b> la répartition dépasse le '
            f'montant du frais de {money(-remaining)}.</font>', st["base"]))

    return _build(path, flow, company, title)


# --------------------------------------------------------------------------- #
# PDF 2 — Gains consolidés par personne
# --------------------------------------------------------------------------- #

def generate_global_pdf(path: str, report: list[dict], company: str, address: str,
                        currency: str, scope_label: str) -> str:
    st = _styles()
    money = lambda v: format_money(v, currency)  # noqa: E731
    title = "Rapport global des gains par intervenant"
    grand_total = round(sum(e["total"] for e in report), 2)
    flow = _header_block(st, company, address, title, [
        f"Périmètre : <b>{_esc(scope_label)}</b>",
    ])
    flow.append(_summary_box(st, [
        ("Intervenants rémunérés", str(len(report)), DARK),
        ("Lignes de répartition", str(sum(len(e["lines"]) for e in report)), DARK),
        ("Total des gains", money(grand_total), ACCENT),
    ]))

    width = PAGE_W - 2 * MARGIN
    if not report:
        flow.append(Spacer(1, 6 * mm))
        flow.append(Paragraph("<i>Aucune répartition sur ce périmètre.</i>", st["base"]))

    for entry in report:
        section = [
            CondPageBreak(45 * mm),
            Paragraph(_esc(entry["name"]), st["h2"]),
            Paragraph("Métier(s) : " + _esc(", ".join(entry["roles"]) or "—")
                      + f" &nbsp;·&nbsp; {entry['nb_projects']} projet(s)", st["small"]),
            Spacer(1, 2 * mm),
        ]
        rows = [[Paragraph("Projet", st["head"]), Paragraph("Frais de production", st["head"]),
                 Paragraph("Métier", st["head"]), Paragraph("Barème", st["head"]),
                 Paragraph("Montant", st["head_r"])]]
        for line in entry["lines"]:
            rows.append([
                Paragraph(_esc(line["project_name"]), st["cell"]),
                Paragraph(_esc(line["expense_label"]), st["cell"]),
                Paragraph(_esc(line.get("role") or "—"), st["cell"]),
                Paragraph(_esc(format_rate(line["rate_type"], line["rate_value"], currency)),
                          st["cell"]),
                Paragraph(money(line["amount"]), st["cell_r"]),
            ])
        rows.append([Paragraph(f"Gain total cumulé — {_esc(entry['name'])}", st["cell_b"]),
                     "", "", "", Paragraph(money(entry["total"]), st["cell_rb"])])
        t = _data_table(rows, [width * 0.24, width * 0.26, width * 0.15, width * 0.18,
                               width * 0.17], total_row=True)
        t.setStyle(TableStyle([("SPAN", (0, -1), (3, -1))]))
        section.append(t)
        flow.extend(section)

    # Récapitulatif final
    if report:
        recap = [Paragraph("Tableau récapitulatif", st["h2"])]
        rows = [[Paragraph("Intervenant", st["head"]), Paragraph("Métier(s)", st["head"]),
                 Paragraph("Projets", st["head_r"]), Paragraph("Gain total", st["head_r"])]]
        for entry in report:
            rows.append([
                Paragraph(_esc(entry["name"]), st["cell_b"]),
                Paragraph(_esc(", ".join(entry["roles"])), st["cell"]),
                Paragraph(str(entry["nb_projects"]), st["cell_r"]),
                Paragraph(money(entry["total"]), st["cell_rb"]),
            ])
        rows.append([Paragraph("TOTAL GÉNÉRAL", st["cell_b"]), "", "",
                     Paragraph(money(grand_total), st["cell_rb"])])
        t = _data_table(rows, [width * 0.3, width * 0.38, width * 0.12, width * 0.2],
                        total_row=True)
        t.setStyle(TableStyle([("SPAN", (0, -1), (2, -1))]))
        recap.append(t)
        flow.append(CondPageBreak(60 * mm))
        flow.append(KeepTogether(recap) if len(rows) < 25 else recap[0])
        if len(rows) >= 25:
            flow.append(t)

    return _build(path, flow, company, title)
