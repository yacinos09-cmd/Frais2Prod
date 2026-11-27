"""
Fenêtre principale : barre d'outils (Annuler / Rétablir / Export / Import /
Devise), onglets Tableau de bord, Projets & Répartitions, Travailleurs &
Barèmes, Rapport Global PDF.
"""
from __future__ import annotations

import os
import traceback
from datetime import date

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QSizePolicy, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QToolBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

import pdf_generator
from database import BackupValidationError, Database
from history import HistoryManager
from ui_dialogs import (
    AllocationDialog, ExpenseDialog, InvoiceDialog, ProjectDialog, SettingsDialog,
    WorkerDialog, configure_table, make_button, repolish,
)
from utils import (
    APP_DISPLAY_NAME, APP_VERSION, CURRENCIES, documents_dir, format_date, format_money,
    format_rate, resource_path, slugify,
)

ROLE_ID = Qt.UserRole
RED = QColor("#DC2626")
GREEN = QColor("#15803D")
AMBER = QColor("#B45309")
MUTED = QColor("#64748B")


# --------------------------------------------------------------------------- #
# Petits utilitaires d'affichage
# --------------------------------------------------------------------------- #

def cell(text, *, data=None, right=False, bold=False, color: QColor | None = None,
         tooltip: str = "") -> QTableWidgetItem:
    it = QTableWidgetItem("" if text is None else str(text))
    if data is not None:
        it.setData(ROLE_ID, data)
    if right:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    if color is not None:
        it.setForeground(color)
    it.setToolTip(tooltip or it.text())
    return it


def selected_id(table: QTableWidget):
    rows = table.selectionModel().selectedRows() if table.selectionModel() else []
    if not rows:
        return None
    it = table.item(rows[0].row(), 0)
    return it.data(ROLE_ID) if it else None


def select_by_id(table: QTableWidget, value) -> bool:
    if value is None:
        return False
    for r in range(table.rowCount()):
        it = table.item(r, 0)
        if it and it.data(ROLE_ID) == value:
            table.selectRow(r)
            return True
    return False


def page_header(title: str, subtitle: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    s = QLabel(subtitle)
    s.setObjectName("PageSubtitle")
    lay.addWidget(t)
    lay.addWidget(s)
    return w


class KpiCard(QFrame):
    def __init__(self, title: str, accent: str = "#4338CA"):
        super().__init__()
        self.setObjectName("KpiCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        bar = QFrame()
        bar.setFixedSize(28, 4)
        bar.setStyleSheet(f"background:{accent}; border-radius:2px;")
        self.title = QLabel(title.upper())
        self.title.setObjectName("KpiTitle")
        self.value = QLabel("—")
        self.value.setObjectName("KpiValue")
        self.hint = QLabel("")
        self.hint.setObjectName("KpiHint")
        lay.addWidget(bar)
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addWidget(self.hint)

    def set(self, value: str, hint: str = "", color: str | None = None):
        self.value.setText(value)
        self.value.setStyleSheet(f"color:{color};" if color else "")
        self.hint.setText(hint)


# --------------------------------------------------------------------------- #
# Onglet 1 : Tableau de bord
# --------------------------------------------------------------------------- #

class DashboardTab(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)
        root.addWidget(page_header("Tableau de bord",
                                   "Vue d'ensemble de l'activité : encaissements, frais et "
                                   "rémunération des intervenants."))
        grid = QGridLayout()
        grid.setSpacing(14)
        self.k_invoiced = KpiCard("Total encaissé", "#4338CA")
        self.k_expenses = KpiCard("Total des frais", "#0EA5E9")
        self.k_allocated = KpiCard("Total réparti", "#15803D")
        self.k_remaining = KpiCard("Reste à répartir", "#F59E0B")
        self.k_margin = KpiCard("Marge brute", "#7C3AED")
        for i, k in enumerate([self.k_invoiced, self.k_expenses, self.k_allocated,
                               self.k_remaining, self.k_margin]):
            grid.addWidget(k, 0, i)
        root.addLayout(grid)

        split = QSplitter(Qt.Horizontal)
        # Gains par intervenant
        box1 = QFrame()
        box1.setObjectName("Card")
        l1 = QVBoxLayout(box1)
        l1.setContentsMargins(16, 14, 16, 14)
        t1 = QLabel("Synthèse des gains par intervenant")
        t1.setObjectName("SectionTitle")
        l1.addWidget(t1)
        self.t_workers = QTableWidget()
        configure_table(self.t_workers, ["Intervenant", "Métier(s)", "Projets", "Gain cumulé",
                                         "Part"], stretch_col=1)
        l1.addWidget(self.t_workers)
        split.addWidget(box1)
        # Synthèse par projet
        box2 = QFrame()
        box2.setObjectName("Card")
        l2 = QVBoxLayout(box2)
        l2.setContentsMargins(16, 14, 16, 14)
        t2 = QLabel("Synthèse par projet")
        t2.setObjectName("SectionTitle")
        l2.addWidget(t2)
        self.t_projects = QTableWidget()
        configure_table(self.t_projects, ["Projet", "Statut", "Encaissé", "Frais", "Réparti",
                                          "Marge"], stretch_col=0, fixed={1: 120})
        self.t_projects.doubleClicked.connect(self._open_project)
        l2.addWidget(self.t_projects)
        split.addWidget(box2)
        split.setSizes([500, 700])
        root.addWidget(split, 1)

    def _open_project(self):
        pid = selected_id(self.t_projects)
        if pid is not None:
            self.main.goto_project(pid)

    def refresh(self):
        db, cur = self.main.db, self.main.currency
        m = lambda v: format_money(v, cur)  # noqa: E731
        s = db.dashboard_stats()
        self.k_invoiced.set(m(s["total_invoiced"]), f"{s['nb_projects']} projet(s)")
        self.k_expenses.set(m(s["total_expenses"]), f"{s['nb_expenses']} frais de production")
        pct = (s["total_allocated"] / s["total_expenses"] * 100) if s["total_expenses"] else 0
        self.k_allocated.set(m(s["total_allocated"]), f"{pct:.0f} % des frais".replace(".", ","))
        rem = s["remaining"]
        self.k_remaining.set(m(rem), "Dépassement !" if rem < 0 else "à affecter",
                             "#DC2626" if rem < 0 else None)
        self.k_margin.set(m(s["margin"]), "encaissé − frais",
                          "#DC2626" if s["margin"] < 0 else None)

        report = db.worker_earnings_report()
        total = sum(e["total"] for e in report) or 1
        self.t_workers.setRowCount(len(report))
        for r, e in enumerate(report):
            self.t_workers.setItem(r, 0, cell(e["name"], data=e["worker_id"], bold=True))
            self.t_workers.setItem(r, 1, cell(", ".join(e["roles"]), color=MUTED))
            self.t_workers.setItem(r, 2, cell(e["nb_projects"], right=True))
            self.t_workers.setItem(r, 3, cell(m(e["total"]), right=True, bold=True))
            self.t_workers.setItem(r, 4, cell(f"{e['total'] / total * 100:.1f} %".replace(".", ","),
                                              right=True, color=MUTED))

        projects = db.list_projects()
        self.t_projects.setRowCount(len(projects))
        for r, p in enumerate(projects):
            self.t_projects.setItem(r, 0, cell(p["name"], data=p["id"], bold=True,
                                               tooltip=p.get("client") or ""))
            self.t_projects.setItem(r, 1, cell(p.get("status") or "", color=MUTED))
            self.t_projects.setItem(r, 2, cell(m(p["total_invoiced"]), right=True))
            self.t_projects.setItem(r, 3, cell(m(p["total_expenses"]), right=True))
            self.t_projects.setItem(r, 4, cell(m(p["total_allocated"]), right=True))
            self.t_projects.setItem(r, 5, cell(m(p["margin"]), right=True, bold=True,
                                               color=RED if p["margin"] < 0 else GREEN))


# --------------------------------------------------------------------------- #
# Onglet 2 : Projets & Répartitions
# --------------------------------------------------------------------------- #

class ProjectsTab(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.setObjectName("Page")
        self._loading = False
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split)

        # ---- Colonne gauche : liste des projets ----
        left = QFrame()
        left.setObjectName("Card")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        ll.setSpacing(10)
        t = QLabel("Projets")
        t.setObjectName("SectionTitle")
        ll.addWidget(t)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Rechercher un projet ou un client…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        ll.addWidget(self.search)
        self.t_projects = QTableWidget()
        configure_table(self.t_projects, ["Projet / client", "Statut"], stretch_col=0,
                        fixed={1: 128})
        self.t_projects.verticalHeader().setDefaultSectionSize(48)
        self.t_projects.itemSelectionChanged.connect(self._on_project_selected)
        self.t_projects.doubleClicked.connect(self.edit_project)
        ll.addWidget(self.t_projects, 1)
        row = QHBoxLayout()
        row.addWidget(make_button("＋ Nouveau projet", "primary", slot=self.add_project))
        self.b_edit_p = make_button("Modifier", slot=self.edit_project)
        self.b_del_p = make_button("Supprimer", "danger", slot=self.delete_project)
        row.addWidget(self.b_edit_p)
        row.addWidget(self.b_del_p)
        ll.addLayout(row)
        split.addWidget(left)

        # ---- Colonne droite : détail ----
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        head = QHBoxLayout()
        self.l_project = QLabel("Sélectionnez un projet")
        self.l_project.setObjectName("ProjectHeader")
        self.l_status = QLabel("")
        self.l_status.setObjectName("Badge")
        self.l_meta = QLabel("")
        self.l_meta.setObjectName("Muted")
        head.addWidget(self.l_project)
        head.addWidget(self.l_status)
        head.addStretch(1)
        head.addWidget(self.l_meta)
        rl.addLayout(head)

        def section(title_widget, total_label, buttons):
            card = QFrame()
            card.setObjectName("Card")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(14, 10, 14, 12)
            lay.setSpacing(8)
            h = QHBoxLayout()
            h.setSpacing(8)
            if total_label is not None:
                h.addWidget(title_widget)
                h.addSpacing(10)
                h.addWidget(total_label)
                h.addStretch(1)
            else:
                h.addWidget(title_widget, 1)
            for b in buttons:
                h.addWidget(b)
            lay.addLayout(h)
            return card, lay

        vsplit = QSplitter(Qt.Vertical)
        vsplit.setChildrenCollapsible(False)

        # Factures clients payées
        ti = QLabel("Factures clients payées")
        ti.setObjectName("SectionTitle")
        self.l_inv_total = QLabel("")
        self.l_inv_total.setObjectName("Muted")
        self.b_add_i = make_button("＋ Facture payée", slot=self.add_invoice)
        self.b_edit_i = make_button("Modifier", slot=self.edit_invoice)
        self.b_del_i = make_button("Supprimer", "danger", slot=self.delete_invoice)
        g_inv, li = section(ti, self.l_inv_total, [self.b_add_i, self.b_edit_i, self.b_del_i])
        self.t_invoices = QTableWidget()
        configure_table(self.t_invoices, ["Référence", "Date d'encaissement", "Montant encaissé",
                                          "Notes"], stretch_col=3)
        self.t_invoices.doubleClicked.connect(self.edit_invoice)
        self.t_invoices.itemSelectionChanged.connect(self._update_buttons)
        li.addWidget(self.t_invoices)
        g_inv.setMinimumHeight(130)
        vsplit.addWidget(g_inv)

        # Frais de production
        te = QLabel("Frais de production")
        te.setObjectName("SectionTitle")
        self.l_exp_total = QLabel("")
        self.l_exp_total.setObjectName("Muted")
        self.b_add_e = make_button("＋ Frais de production", slot=self.add_expense)
        self.b_edit_e = make_button("Modifier", slot=self.edit_expense)
        self.b_del_e = make_button("Supprimer", "danger", slot=self.delete_expense)
        g_exp, le = section(te, self.l_exp_total, [self.b_add_e, self.b_edit_e, self.b_del_e])
        self.t_expenses = QTableWidget()
        configure_table(self.t_expenses, ["Intitulé", "Catégorie", "Facture client", "Montant",
                                          "Réparti", "Reste à répartir"], stretch_col=0,
                        fixed={1: 140, 2: 130})
        self.t_expenses.itemSelectionChanged.connect(self._on_expense_selected)
        self.t_expenses.doubleClicked.connect(self.edit_expense)
        le.addWidget(self.t_expenses)
        g_exp.setMinimumHeight(150)
        vsplit.addWidget(g_exp)

        # Répartition du frais sélectionné
        self.l_alloc_title = QLabel("Répartition du frais")
        self.l_alloc_title.setObjectName("SectionTitle")
        self.b_add_a = make_button("＋ Affecter un intervenant", slot=self.add_allocation)
        self.b_edit_a = make_button("Modifier", slot=self.edit_allocation)
        self.b_del_a = make_button("Retirer", "danger", slot=self.delete_allocation)
        self.b_pdf = make_button("📄  Exporter PDF du frais", "primary",
                                 tooltip="Génère le PDF détaillé de la répartition de ce frais",
                                 slot=self.export_expense_pdf)
        self.l_alloc_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        g_al, la = section(self.l_alloc_title, None,
                           [self.b_add_a, self.b_edit_a, self.b_del_a])
        pills = QHBoxLayout()
        pills.setSpacing(10)
        self.p_total = QLabel("Montant : —")
        self.p_alloc = QLabel("Réparti : —")
        self.p_rest = QLabel("Reste à répartir : —")
        for p in (self.p_total, self.p_alloc, self.p_rest):
            p.setObjectName("Pill")
            pills.addWidget(p)
        pills.addStretch(1)
        pills.addWidget(self.b_pdf)
        la.addLayout(pills)
        prog = QHBoxLayout()
        prog.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000)
        self.l_alloc_warn = QLabel("")
        prog.addWidget(self.progress, 1)
        prog.addWidget(self.l_alloc_warn)
        la.addLayout(prog)
        self.t_alloc = QTableWidget()
        configure_table(self.t_alloc, ["Intervenant", "Métier", "Barème appliqué", "Part",
                                       "Montant dû", "Note"], stretch_col=5)
        self.t_alloc.doubleClicked.connect(self.edit_allocation)
        self.t_alloc.itemSelectionChanged.connect(self._update_buttons)
        la.addWidget(self.t_alloc, 1)
        g_al.setMinimumHeight(220)
        vsplit.addWidget(g_al)
        vsplit.setSizes([165, 225, 400])
        rl.addWidget(vsplit, 1)
        split.addWidget(right)
        split.setSizes([350, 1050])
        split.setStretchFactor(1, 1)

    # ---------------------------------------------------------------- #
    # Sélection / rafraîchissement
    # ---------------------------------------------------------------- #
    def current_project_id(self):
        return selected_id(self.t_projects)

    def current_expense_id(self):
        return selected_id(self.t_expenses)

    def refresh(self):
        pid = self.current_project_id()
        eid = self.current_expense_id()
        self._loading = True
        projects = self.main.db.list_projects()
        self.t_projects.setRowCount(len(projects))
        for r, p in enumerate(projects):
            sub = " · ".join(x for x in (p.get("client"), format_date(p.get("date"))) if x)
            it = cell(f"{p['name']}\n{sub}", data=p["id"],
                      tooltip=f"{p['name']}\nClient : {p.get('client') or '—'}\n"
                              f"Date : {format_date(p.get('date'))}")
            self.t_projects.setItem(r, 0, it)
            self.t_projects.setItem(r, 1, cell(p.get("status") or "", color=MUTED))
        self._apply_filter()
        self._loading = False
        if not select_by_id(self.t_projects, pid) and self.t_projects.rowCount():
            for r in range(self.t_projects.rowCount()):
                if not self.t_projects.isRowHidden(r):
                    self.t_projects.selectRow(r)
                    break
        self._load_project(keep_expense=eid)

    def select_project(self, pid):
        select_by_id(self.t_projects, pid)

    def _apply_filter(self):
        q = self.search.text().strip().lower()
        for r in range(self.t_projects.rowCount()):
            txt = " ".join((self.t_projects.item(r, c).toolTip() if self.t_projects.item(r, c) else "")
                           for c in range(self.t_projects.columnCount())).lower()
            self.t_projects.setRowHidden(r, bool(q) and q not in txt)

    def _on_project_selected(self):
        if not self._loading:
            self._load_project()

    def _load_project(self, keep_expense=None):
        db, cur = self.main.db, self.main.currency
        m = lambda v: format_money(v, cur)  # noqa: E731
        pid = self.current_project_id()
        project = db.get_project(pid) if pid is not None else None
        self._loading = True
        if not project:
            self.l_project.setText("Aucun projet sélectionné")
            self.l_status.setVisible(False)
            self.l_meta.setText("")
            self.t_invoices.setRowCount(0)
            self.t_expenses.setRowCount(0)
            self.l_inv_total.setText("")
            self.l_exp_total.setText("")
            self._loading = False
            self._load_allocations()
            return
        self.l_project.setText(project["name"])
        self.l_project.setToolTip(project.get("notes") or "")
        self.l_status.setText(project.get("status") or "—")
        self.l_status.setVisible(True)
        self.l_meta.setText(f"Client : {project.get('client') or '—'}   ·   "
                            f"{format_date(project.get('date'))}")

        invoices = db.list_invoices(pid)
        self.t_invoices.setRowCount(len(invoices))
        for r, inv in enumerate(invoices):
            self.t_invoices.setItem(r, 0, cell(inv["reference"], data=inv["id"], bold=True,
                                               tooltip=inv.get("notes") or ""))
            self.t_invoices.setItem(r, 1, cell(format_date(inv.get("date"))))
            self.t_invoices.setItem(r, 2, cell(m(inv["amount"]), right=True, bold=True))
            self.t_invoices.setItem(r, 3, cell(inv.get("notes") or "", color=MUTED))
        self.l_inv_total.setText(f"Total encaissé : <b>{m(sum(i['amount'] for i in invoices))}</b>")

        expenses = db.list_expenses(pid)
        self.t_expenses.setRowCount(len(expenses))
        for r, e in enumerate(expenses):
            rest = e["remaining"]
            color = RED if rest < -0.005 else (GREEN if abs(rest) < 0.005 else AMBER)
            tip = e["label"] + f"\nFacture associée : {e.get('invoice_reference') or 'aucune'}"
            if e.get("notes"):
                tip += f"\nNote : {e['notes']}"
            self.t_expenses.setItem(r, 0, cell(e["label"], data=e["id"], bold=True, tooltip=tip))
            self.t_expenses.setItem(r, 1, cell(e.get("category") or "", color=MUTED))
            self.t_expenses.setItem(r, 2, cell(e.get("invoice_reference") or "—", color=MUTED))
            self.t_expenses.setItem(r, 3, cell(m(e["amount"]), right=True))
            self.t_expenses.setItem(r, 4, cell(m(e["allocated"]), right=True))
            self.t_expenses.setItem(r, 5, cell(m(rest), right=True, bold=True, color=color))
        tot_e = sum(e["amount"] for e in expenses)
        self.l_exp_total.setText(f"Total des frais : <b>{m(tot_e)}</b>")
        self._loading = False
        if not select_by_id(self.t_expenses, keep_expense) and expenses:
            self.t_expenses.selectRow(0)
        self._load_allocations()

    def _on_expense_selected(self):
        if not self._loading:
            self._load_allocations()

    def _set_pill(self, label: QLabel, state: str):
        label.setProperty("state", state)
        repolish(label)

    def _load_allocations(self):
        db, cur = self.main.db, self.main.currency
        m = lambda v: format_money(v, cur)  # noqa: E731
        eid = self.current_expense_id()
        expense = db.get_expense(eid) if eid is not None else None
        aid = selected_id(self.t_alloc)
        if not expense:
            self.l_alloc_title.setText("Répartition du frais")
            self.t_alloc.setRowCount(0)
            self.p_total.setText("Montant : —")
            self.p_alloc.setText("Réparti : —")
            self.p_rest.setText("Reste à répartir : —")
            self._set_pill(self.p_rest, "")
            self.progress.setValue(0)
            self.l_alloc_warn.setText("Sélectionnez ou créez un frais de production pour le répartir.")
            self._update_buttons()
            return
        self.l_alloc_title.setText(f"Répartition — {expense['label']}")
        allocs = db.list_allocations(eid)
        self.t_alloc.setRowCount(len(allocs))
        for r, a in enumerate(allocs):
            share = a["amount"] / expense["amount"] * 100 if expense["amount"] else 0
            self.t_alloc.setItem(r, 0, cell(a["worker_name"], data=a["id"], bold=True))
            self.t_alloc.setItem(r, 1, cell(a.get("role") or "—"))
            self.t_alloc.setItem(r, 2, cell(format_rate(a["rate_type"], a["rate_value"], cur),
                                            color=MUTED))
            self.t_alloc.setItem(r, 3, cell(f"{share:.1f} %".replace(".", ","), right=True,
                                            color=MUTED))
            self.t_alloc.setItem(r, 4, cell(m(a["amount"]), right=True, bold=True))
            self.t_alloc.setItem(r, 5, cell(a.get("notes") or "", color=MUTED))
        select_by_id(self.t_alloc, aid)

        rest = expense["remaining"]
        self.p_total.setText(f"Montant : {m(expense['amount'])}")
        self.p_alloc.setText(f"Réparti : {m(expense['allocated'])}")
        self.p_rest.setText(f"Reste à répartir : {m(rest)}")
        state = "error" if rest < -0.005 else ("ok" if abs(rest) < 0.005 else "warn")
        self._set_pill(self.p_rest, state)
        ratio = expense["allocated"] / expense["amount"] if expense["amount"] else 0
        self.progress.setValue(int(min(ratio, 1.0) * 1000))
        self.progress.setProperty("state", state if state != "warn" else "")
        repolish(self.progress)
        if state == "error":
            self.l_alloc_warn.setText(
                f"<span style='color:#DC2626'><b>⚠ Attention :</b> la répartition dépasse le "
                f"montant disponible de {m(-rest)}.</span>")
        elif state == "ok":
            self.l_alloc_warn.setText("<span style='color:#15803D'>✔ Frais entièrement réparti.</span>")
        else:
            self.l_alloc_warn.setText(f"<span style='color:#64748B'>{ratio * 100:.0f} % du frais "
                                      f"réparti</span>")
        self._update_buttons()

    def _update_buttons(self):
        has_p = self.current_project_id() is not None
        has_e = self.current_expense_id() is not None
        self.b_edit_p.setEnabled(has_p)
        self.b_del_p.setEnabled(has_p)
        self.b_add_i.setEnabled(has_p)
        self.b_edit_i.setEnabled(selected_id(self.t_invoices) is not None)
        self.b_del_i.setEnabled(selected_id(self.t_invoices) is not None)
        self.b_add_e.setEnabled(has_p)
        self.b_edit_e.setEnabled(has_e)
        self.b_del_e.setEnabled(has_e)
        self.b_add_a.setEnabled(has_e)
        self.b_pdf.setEnabled(has_e)
        has_a = selected_id(self.t_alloc) is not None
        self.b_edit_a.setEnabled(has_a)
        self.b_del_a.setEnabled(has_a)

    # ---------------------------------------------------------------- #
    # Actions : projets
    # ---------------------------------------------------------------- #
    def _clients(self):
        return [p.get("client") for p in self.main.db.list_projects()]

    def add_project(self):
        dlg = ProjectDialog(self, clients=self._clients())
        if dlg.exec():
            data = dlg.get_data()
            new_id = self.main.run(f"Ajout du projet « {data['name']} »",
                                   self.main.db.add_project, data)
            self.select_project(new_id)

    def edit_project(self, *_):
        pid = self.current_project_id()
        if pid is None:
            return
        dlg = ProjectDialog(self, self.main.db.get_project(pid), clients=self._clients())
        if dlg.exec():
            data = dlg.get_data()
            self.main.run(f"Modification du projet « {data['name']} »",
                          self.main.db.update_project, pid, data)

    def delete_project(self):
        pid = self.current_project_id()
        if pid is None:
            return
        p = self.main.db.get_project(pid)
        if self.main.confirm("Supprimer le projet",
                             f"Supprimer le projet « {p['name']} » ainsi que ses factures, frais "
                             "et répartitions ?\n\nVous pourrez annuler cette action (Ctrl+Z)."):
            self.main.run(f"Suppression du projet « {p['name']} »",
                          self.main.db.delete_project, pid)

    # ---------------------------------------------------------------- #
    # Actions : factures
    # ---------------------------------------------------------------- #
    def add_invoice(self):
        pid = self.current_project_id()
        if pid is None:
            return
        p = self.main.db.get_project(pid)
        n = len(self.main.db.list_invoices(pid)) + 1
        dlg = InvoiceDialog(self, self.main.currency, p["name"],
                            suggested_ref=f"FAC-{date.today().year}-{pid:02d}{n:02d}")
        if dlg.exec():
            data = dlg.get_data() | {"project_id": pid}
            self.main.run(f"Ajout de la facture « {data['reference']} »",
                          self.main.db.add_invoice, data)

    def edit_invoice(self, *_):
        iid = selected_id(self.t_invoices)
        if iid is None:
            return
        inv = self.main.db.get_invoice(iid)
        p = self.main.db.get_project(inv["project_id"])
        dlg = InvoiceDialog(self, self.main.currency, p["name"], inv)
        if dlg.exec():
            data = dlg.get_data()
            self.main.run(f"Modification de la facture « {data['reference']} »",
                          self.main.db.update_invoice, iid, data)

    def delete_invoice(self):
        iid = selected_id(self.t_invoices)
        if iid is None:
            return
        inv = self.main.db.get_invoice(iid)
        if self.main.confirm("Supprimer la facture",
                             f"Supprimer la facture « {inv['reference']} » ?\nLes frais associés "
                             "seront conservés mais ne seront plus rattachés à cette facture."):
            self.main.run(f"Suppression de la facture « {inv['reference']} »",
                          self.main.db.delete_invoice, iid)

    # ---------------------------------------------------------------- #
    # Actions : frais
    # ---------------------------------------------------------------- #
    def add_expense(self):
        pid = self.current_project_id()
        if pid is None:
            return
        db = self.main.db
        p = db.get_project(pid)
        dlg = ExpenseDialog(self, self.main.currency, p["name"], db.list_invoices(pid))
        if dlg.exec():
            data = dlg.get_data() | {"project_id": pid}
            new_id = self.main.run(f"Ajout du frais « {data['label']} »", db.add_expense, data)
            select_by_id(self.t_expenses, new_id)

    def edit_expense(self, *_):
        eid = self.current_expense_id()
        if eid is None:
            return
        db = self.main.db
        e = db.get_expense(eid)
        dlg = ExpenseDialog(self, self.main.currency, e["project_name"],
                            db.list_invoices(e["project_id"]), e, db.list_allocations(eid))
        if dlg.exec():
            data = dlg.get_data()
            self.main.run(f"Modification du frais « {data['label']} »",
                          db.update_expense, eid, data)

    def delete_expense(self):
        eid = self.current_expense_id()
        if eid is None:
            return
        e = self.main.db.get_expense(eid)
        if self.main.confirm("Supprimer le frais",
                             f"Supprimer le frais « {e['label']} » et toutes ses répartitions ?"):
            self.main.run(f"Suppression du frais « {e['label']} »",
                          self.main.db.delete_expense, eid)

    # ---------------------------------------------------------------- #
    # Actions : répartitions
    # ---------------------------------------------------------------- #
    def add_allocation(self):
        eid = self.current_expense_id()
        if eid is None:
            return
        db = self.main.db
        if not db.list_workers():
            QMessageBox.information(self, "Aucun intervenant",
                                    "Ajoutez d'abord des intervenants dans l'onglet "
                                    "« Travailleurs & Barèmes ».")
            return
        dlg = AllocationDialog(self, db, self.main.currency, db.get_expense(eid))
        if dlg.exec():
            new_id = self.main.run(f"Répartition vers « {dlg.worker_name()} »",
                                   db.add_allocation, dlg.get_data())
            select_by_id(self.t_alloc, new_id)

    def edit_allocation(self, *_):
        aid = selected_id(self.t_alloc)
        eid = self.current_expense_id()
        if aid is None or eid is None:
            return
        db = self.main.db
        alloc = next((a for a in db.list_allocations(eid) if a["id"] == aid), None)
        dlg = AllocationDialog(self, db, self.main.currency, db.get_expense(eid), alloc)
        if dlg.exec():
            self.main.run(f"Modification de la répartition de « {dlg.worker_name()} »",
                          db.update_allocation, aid, dlg.get_data())

    def delete_allocation(self):
        aid = selected_id(self.t_alloc)
        eid = self.current_expense_id()
        if aid is None:
            return
        alloc = next((a for a in self.main.db.list_allocations(eid) if a["id"] == aid), None)
        if alloc and self.main.confirm("Retirer l'intervenant",
                                       f"Retirer « {alloc['worker_name']} » de la répartition ?"):
            self.main.run(f"Retrait de « {alloc['worker_name']} » de la répartition",
                          self.main.db.delete_allocation, aid)

    # ---------------------------------------------------------------- #
    # PDF du frais
    # ---------------------------------------------------------------- #
    def export_expense_pdf(self):
        eid = self.current_expense_id()
        if eid is None:
            return
        db = self.main.db
        e = db.get_expense(eid)
        default = os.path.join(
            self.main.last_dir,
            f"frais-{slugify(e['project_name'], 25)}-{slugify(e['label'], 25)}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le PDF du frais", default,
                                              "Document PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            pdf_generator.generate_expense_pdf(
                path, e, db.list_allocations(eid), self.main.company_name,
                self.main.company_address, self.main.currency)
        except Exception as exc:  # pragma: no cover - affichage d'erreur
            self.main.error("Erreur lors de la génération du PDF", exc)
            return
        self.main.pdf_done(path)


# --------------------------------------------------------------------------- #
# Onglet 3 : Travailleurs & Barèmes
# --------------------------------------------------------------------------- #

class WorkersTab(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(page_header("Travailleurs & Barèmes",
                                   "Référentiel central des intervenants, réutilisable dans "
                                   "tous les projets."))
        head.addStretch(1)
        head.addWidget(make_button("＋ Nouvel intervenant", "primary", slot=self.add_worker))
        root.addLayout(head)

        split = QSplitter(Qt.Horizontal)
        left = QFrame()
        left.setObjectName("Card")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Rechercher par nom ou métier…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        ll.addWidget(self.search)
        self.table = QTableWidget()
        configure_table(self.table, ["Nom", "Métier(s)", "Contact", "Projets", "Gains cumulés"],
                        stretch_col=1)
        self.table.itemSelectionChanged.connect(self._load_detail)
        self.table.doubleClicked.connect(self.edit_worker)
        ll.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.b_edit = make_button("Modifier", slot=self.edit_worker)
        self.b_del = make_button("Supprimer", "danger", slot=self.delete_worker)
        row.addWidget(self.b_edit)
        row.addWidget(self.b_del)
        row.addStretch(1)
        ll.addLayout(row)
        split.addWidget(left)

        right = QFrame()
        right.setObjectName("Card")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 14, 16, 14)
        self.l_name = QLabel("—")
        self.l_name.setObjectName("ProjectHeader")
        self.l_contact = QLabel("")
        self.l_contact.setObjectName("Muted")
        self.l_contact.setWordWrap(True)
        rl.addWidget(self.l_name)
        rl.addWidget(self.l_contact)
        rl.addSpacing(8)
        t1 = QLabel("Barèmes par métier")
        t1.setObjectName("SectionTitle")
        rl.addWidget(t1)
        self.t_roles = QTableWidget()
        configure_table(self.t_roles, ["Métier", "Type", "Barème par défaut"], stretch_col=0)
        self.t_roles.setMaximumHeight(190)
        rl.addWidget(self.t_roles)
        rl.addSpacing(8)
        t2 = QLabel("Participations")
        t2.setObjectName("SectionTitle")
        rl.addWidget(t2)
        self.t_parts = QTableWidget()
        configure_table(self.t_parts, ["Projet", "Frais", "Métier", "Montant"], stretch_col=1)
        rl.addWidget(self.t_parts, 1)
        self.l_total = QLabel("")
        self.l_total.setAlignment(Qt.AlignRight)
        self.l_total.setObjectName("SectionTitle")
        rl.addWidget(self.l_total)
        split.addWidget(right)
        split.setSizes([700, 520])
        root.addWidget(split, 1)

    def refresh(self):
        wid = selected_id(self.table)
        cur = self.main.currency
        workers = self.main.db.list_workers()
        self.table.blockSignals(True)
        self.table.setRowCount(len(workers))
        for r, w in enumerate(workers):
            self.table.setItem(r, 0, cell(w["name"], data=w["id"], bold=True))
            self.table.setItem(r, 1, cell(", ".join(x["role"] for x in w["roles"])))
            self.table.setItem(r, 2, cell(w.get("phone") or w.get("email") or "", color=MUTED,
                                          tooltip=w.get("email") or ""))
            self.table.setItem(r, 3, cell(w["nb_projects"], right=True))
            self.table.setItem(r, 4, cell(format_money(w["total_earned"], cur), right=True,
                                          bold=True))
        self.table.blockSignals(False)
        self._apply_filter()
        if not select_by_id(self.table, wid) and workers:
            self.table.selectRow(0)
        self._load_detail()

    def _apply_filter(self):
        q = self.search.text().strip().lower()
        for r in range(self.table.rowCount()):
            txt = f"{self.table.item(r, 0).text()} {self.table.item(r, 1).text()}".lower()
            self.table.setRowHidden(r, bool(q) and q not in txt)

    def _load_detail(self):
        wid = selected_id(self.table)
        self.b_edit.setEnabled(wid is not None)
        self.b_del.setEnabled(wid is not None)
        cur = self.main.currency
        w = self.main.db.get_worker(wid) if wid is not None else None
        if not w:
            self.l_name.setText("Aucun intervenant sélectionné")
            self.l_contact.setText("")
            self.t_roles.setRowCount(0)
            self.t_parts.setRowCount(0)
            self.l_total.setText("")
            return
        self.l_name.setText(w["name"])
        contact = "   ·   ".join(x for x in (w.get("email"), w.get("phone")) if x)
        if w.get("notes"):
            contact += ("\n" if contact else "") + w["notes"]
        self.l_contact.setText(contact)
        self.t_roles.setRowCount(len(w["roles"]))
        for r, role in enumerate(w["roles"]):
            self.t_roles.setItem(r, 0, cell(role["role"], bold=True))
            self.t_roles.setItem(r, 1, cell("Pourcentage" if role["rate_type"] == "percent"
                                            else "Montant fixe", color=MUTED))
            self.t_roles.setItem(r, 2, cell(format_rate(role["rate_type"], role["rate_value"], cur)))
        report = [e for e in self.main.db.worker_earnings_report() if e["worker_id"] == wid]
        lines = report[0]["lines"] if report else []
        self.t_parts.setRowCount(len(lines))
        for r, ln in enumerate(lines):
            self.t_parts.setItem(r, 0, cell(ln["project_name"]))
            self.t_parts.setItem(r, 1, cell(ln["expense_label"]))
            self.t_parts.setItem(r, 2, cell(ln.get("role") or "—", color=MUTED))
            self.t_parts.setItem(r, 3, cell(format_money(ln["amount"], cur), right=True))
        total = report[0]["total"] if report else 0
        self.l_total.setText(f"Gain total cumulé : {format_money(total, cur)}")

    def add_worker(self):
        dlg = WorkerDialog(self, self.main.currency,
                           role_suggestions=self.main.db.all_role_names())
        if dlg.exec():
            data, roles = dlg.get_data(), dlg.get_roles()
            new_id = self.main.run(f"Ajout de l'intervenant « {data['name']} »",
                                   self.main.db.add_worker, data, roles)
            select_by_id(self.table, new_id)

    def edit_worker(self, *_):
        wid = selected_id(self.table)
        if wid is None:
            return
        dlg = WorkerDialog(self, self.main.currency, self.main.db.get_worker(wid),
                           role_suggestions=self.main.db.all_role_names())
        if dlg.exec():
            data, roles = dlg.get_data(), dlg.get_roles()
            self.main.run(f"Modification de l'intervenant « {data['name']} »",
                          self.main.db.update_worker, wid, data, roles)

    def delete_worker(self):
        wid = selected_id(self.table)
        if wid is None:
            return
        w = self.main.db.get_worker(wid)
        n = self.main.db.count_worker_allocations(wid)
        extra = (f"\n\n⚠ Cet intervenant figure dans {n} répartition(s), qui seront également "
                 "supprimées." if n else "")
        if self.main.confirm("Supprimer l'intervenant",
                             f"Supprimer « {w['name']} » du référentiel ?{extra}\n\n"
                             "Vous pourrez annuler cette action (Ctrl+Z)."):
            self.main.run(f"Suppression de l'intervenant « {w['name']} »",
                          self.main.db.delete_worker, wid)


# --------------------------------------------------------------------------- #
# Onglet 4 : Rapport Global PDF
# --------------------------------------------------------------------------- #

class ReportTab(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(page_header("Rapport global des gains",
                                   "Gains consolidés par intervenant, sur un projet ou sur "
                                   "l'ensemble des projets."))
        head.addStretch(1)
        lbl = QLabel("Périmètre :")
        lbl.setObjectName("Muted")
        head.addWidget(lbl)
        self.filter = QComboBox()
        self.filter.setMinimumWidth(280)
        self.filter.currentIndexChanged.connect(self._load)
        head.addWidget(self.filter)
        self.b_pdf = make_button("📄  Générer le PDF Global", "primary", slot=self.export_pdf)
        head.addWidget(self.b_pdf)
        root.addLayout(head)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 14, 14, 14)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Intervenant / Projet", "Frais de production", "Métier",
                                   "Barème", "Montant"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        hh = self.tree.header()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in (2, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        cl.addWidget(self.tree, 1)
        foot = QHBoxLayout()
        self.l_summary = QLabel("")
        self.l_summary.setObjectName("Muted")
        self.l_total = QLabel("")
        self.l_total.setObjectName("SectionTitle")
        foot.addWidget(self.l_summary)
        foot.addStretch(1)
        foot.addWidget(self.l_total)
        cl.addLayout(foot)
        root.addWidget(card, 1)

    def refresh(self):
        current = self.filter.currentData()
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.addItem("Tous les projets", None)
        for p in self.main.db.list_projects():
            self.filter.addItem(p["name"], p["id"])
        idx = self.filter.findData(current)
        self.filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.filter.blockSignals(False)
        self._load()

    def _report(self):
        return self.main.db.worker_earnings_report(self.filter.currentData())

    def _load(self, *_):
        cur = self.main.currency
        m = lambda v: format_money(v, cur)  # noqa: E731
        report = self._report()
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)
        for e in report:
            top = QTreeWidgetItem([e["name"], f"{len(e['lines'])} ligne(s) · "
                                   f"{e['nb_projects']} projet(s)", ", ".join(e["roles"]), "",
                                   m(e["total"])])
            for c in range(5):
                top.setFont(c, bold)
            top.setForeground(1, MUTED)
            top.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)
            top.setSizeHint(0, QSize(0, 34))
            for ln in e["lines"]:
                child = QTreeWidgetItem([ln["project_name"], ln["expense_label"],
                                         ln.get("role") or "—",
                                         format_rate(ln["rate_type"], ln["rate_value"], cur),
                                         m(ln["amount"])])
                child.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)
                child.setSizeHint(0, QSize(0, 28))
                child.setForeground(3, MUTED)
                top.addChild(child)
            self.tree.addTopLevelItem(top)
        self.tree.expandAll()
        total = sum(e["total"] for e in report)
        self.l_summary.setText(f"{len(report)} intervenant(s) rémunéré(s) · "
                               f"{sum(len(e['lines']) for e in report)} ligne(s) de répartition")
        self.l_total.setText(f"Total des gains : {m(total)}")
        self.b_pdf.setEnabled(True)

    def export_pdf(self):
        scope = self.filter.currentText()
        suffix = "tous-projets" if self.filter.currentData() is None else slugify(scope, 30)
        default = os.path.join(self.main.last_dir,
                               f"rapport-gains-{suffix}-{date.today().isoformat()}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport global", default,
                                              "Document PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            pdf_generator.generate_global_pdf(path, self._report(), self.main.company_name,
                                              self.main.company_address, self.main.currency,
                                              scope)
        except Exception as exc:  # pragma: no cover
            self.main.error("Erreur lors de la génération du PDF", exc)
            return
        self.main.pdf_done(path)


# --------------------------------------------------------------------------- #
# Fenêtre principale
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.history = HistoryManager(db)
        self.history.subscribe(self._update_history_actions)
        self.last_dir = documents_dir()
        self.setWindowTitle(f"{APP_DISPLAY_NAME} — {self.company_name}")
        icon_path = resource_path(os.path.join("assets", "icon.png"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        self._build_actions()
        self._build_toolbar()
        self._build_menus()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.dashboard = DashboardTab(self)
        self.projects = ProjectsTab(self)
        self.workers = WorkersTab(self)
        self.report = ReportTab(self)
        self.tabs.addTab(self.dashboard, "📊  Tableau de bord")
        self.tabs.addTab(self.projects, "🎬  Projets && Répartitions")
        self.tabs.addTab(self.workers, "👥  Travailleurs && Barèmes")
        self.tabs.addTab(self.report, "📄  Rapport Global PDF")
        self.setCentralWidget(self.tabs)

        sb = self.statusBar()
        self.l_db = QLabel()
        self.l_db.setToolTip(self.db.path)
        self.l_db.setText(f"Base : {os.path.basename(self.db.path)}")
        sb.addPermanentWidget(self.l_db)
        self.refresh_all()
        self._update_history_actions()
        self.status("Prêt.")

    # ---------------------------------------------------------------- #
    # Propriétés
    # ---------------------------------------------------------------- #
    @property
    def currency(self) -> str:
        return self.db.get_setting("currency", "FDJ")

    @property
    def company_name(self) -> str:
        return self.db.get_setting("company_name", "Ma Société de Production")

    @property
    def company_address(self) -> str:
        return self.db.get_setting("company_address", "")

    # ---------------------------------------------------------------- #
    # Construction de l'interface
    # ---------------------------------------------------------------- #
    def _build_actions(self):
        self.a_undo = QAction("↩  Annuler", self)
        self.a_undo.setShortcuts([QKeySequence(QKeySequence.Undo)])
        self.a_undo.triggered.connect(self.undo)
        self.a_redo = QAction("↪  Rétablir", self)
        redo_keys = [QKeySequence(QKeySequence.Redo), QKeySequence("Ctrl+Y"),
                     QKeySequence("Ctrl+Shift+Z")]
        uniq = []
        for k in redo_keys:
            if k.toString() and k.toString() not in [u.toString() for u in uniq]:
                uniq.append(k)
        self.a_redo.setShortcuts(uniq)
        self.a_redo.triggered.connect(self.redo)
        self.a_export = QAction("⬆  Exporter BDD", self)
        self.a_export.setShortcut(QKeySequence("Ctrl+E"))
        self.a_export.setToolTip("Exporter toute la base (JSON horodaté ou copie .db)")
        self.a_export.triggered.connect(self.export_db)
        self.a_import = QAction("⬇  Importer BDD", self)
        self.a_import.setShortcut(QKeySequence("Ctrl+I"))
        self.a_import.setToolTip("Importer une sauvegarde JSON (ou .db) — annulable")
        self.a_import.triggered.connect(self.import_db)
        self.a_demo = QAction("⟳  Données de démo", self)
        self.a_demo.setToolTip("Réinitialiser avec le jeu de données de démonstration (annulable)")
        self.a_demo.triggered.connect(self.reset_demo)
        self.a_settings = QAction("⚙  Paramètres", self)
        self.a_settings.setShortcut(QKeySequence(QKeySequence.Preferences))
        self.a_settings.triggered.connect(self.edit_settings)
        self.a_clear = QAction("Vider toutes les données…", self)
        self.a_clear.triggered.connect(self.clear_data)
        self.a_quit = QAction("Quitter", self)
        self.a_quit.setShortcut(QKeySequence(QKeySequence.Quit))
        self.a_quit.triggered.connect(self.close)
        self.a_about = QAction("À propos", self)
        self.a_about.triggered.connect(self.about)
        self.a_open_folder = QAction("Ouvrir le dossier des données", self)
        self.a_open_folder.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.db.path))))
        for a in (self.a_undo, self.a_redo, self.a_export, self.a_import):
            a.setShortcutContext(Qt.ApplicationShortcut)

    def _build_toolbar(self):
        tb = QToolBar("Barre d'outils principale")
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(Qt.TopToolBarArea, tb)
        title = QLabel("🎞  " + APP_DISPLAY_NAME)
        title.setObjectName("AppTitle")
        tb.addWidget(title)
        tb.addAction(self.a_undo)
        tb.addAction(self.a_redo)
        tb.addSeparator()
        tb.addAction(self.a_export)
        tb.addAction(self.a_import)
        tb.addSeparator()
        tb.addAction(self.a_demo)
        tb.addAction(self.a_settings)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        tb.addWidget(QLabel("Devise :"))
        self.cb_currency = QComboBox()
        for code, (label, _) in CURRENCIES.items():
            self.cb_currency.addItem(code, code)
            self.cb_currency.setItemData(self.cb_currency.count() - 1, label, Qt.ToolTipRole)
        self.cb_currency.setToolTip("Devise d'affichage des montants (sans conversion)")
        self.cb_currency.setCurrentIndex(max(0, self.cb_currency.findData(self.currency)))
        self.cb_currency.currentIndexChanged.connect(self._on_currency_changed)
        tb.addWidget(self.cb_currency)

    def _build_menus(self):
        mb = self.menuBar()
        m_file = mb.addMenu("&Fichier")
        m_file.addAction(self.a_export)
        m_file.addAction(self.a_import)
        m_file.addSeparator()
        m_file.addAction(self.a_settings)
        m_file.addAction(self.a_open_folder)
        m_file.addSeparator()
        m_file.addAction(self.a_demo)
        m_file.addAction(self.a_clear)
        m_file.addSeparator()
        m_file.addAction(self.a_quit)
        m_edit = mb.addMenu("&Édition")
        m_edit.addAction(self.a_undo)
        m_edit.addAction(self.a_redo)
        m_help = mb.addMenu("&Aide")
        m_help.addAction(self.a_about)

    # ---------------------------------------------------------------- #
    # Exécution des opérations (avec historique)
    # ---------------------------------------------------------------- #
    def run(self, description: str, func, *args, **kwargs):
        self.last_run_ok = False
        try:
            result = self.history.execute(description, func, *args, **kwargs)
        except Exception as exc:
            self.error("L'opération n'a pas pu être effectuée", exc)
            self.refresh_all()
            return None
        self.last_run_ok = True
        self.refresh_all()
        self.status(f"✔ {description}")
        return result

    def undo(self):
        desc = self.history.undo()
        if desc:
            self.refresh_all()
            self.status(f"↩ Annulé : {desc}")
        else:
            self.status("Rien à annuler.")

    def redo(self):
        desc = self.history.redo()
        if desc:
            self.refresh_all()
            self.status(f"↪ Rétabli : {desc}")
        else:
            self.status("Rien à rétablir.")

    def _update_history_actions(self):
        h = self.history
        self.a_undo.setEnabled(h.can_undo())
        self.a_redo.setEnabled(h.can_redo())
        self.a_undo.setToolTip(f"Annuler : {h.undo_text()}  ({self.a_undo.shortcut().toString(QKeySequence.NativeText)})"
                               if h.can_undo() else "Rien à annuler")
        self.a_redo.setToolTip(f"Rétablir : {h.redo_text()}  ({self.a_redo.shortcut().toString(QKeySequence.NativeText)})"
                               if h.can_redo() else "Rien à rétablir")

    def refresh_all(self):
        self.setWindowTitle(f"{APP_DISPLAY_NAME} — {self.company_name}")
        self.dashboard.refresh()
        self.projects.refresh()
        self.workers.refresh()
        self.report.refresh()

    def goto_project(self, pid):
        self.tabs.setCurrentWidget(self.projects)
        self.projects.search.clear()
        self.projects.select_project(pid)

    # ---------------------------------------------------------------- #
    # Messages
    # ---------------------------------------------------------------- #
    def status(self, msg: str, timeout: int = 6000):
        self.statusBar().showMessage(msg, timeout)

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.Yes | QMessageBox.No, self)
        box.button(QMessageBox.Yes).setText("Oui, confirmer")
        box.button(QMessageBox.No).setText("Non")
        box.setDefaultButton(QMessageBox.No)
        return box.exec() == QMessageBox.Yes

    def error(self, title: str, exc: Exception):
        box = QMessageBox(QMessageBox.Critical, title, str(exc), QMessageBox.Ok, self)
        box.setDetailedText(traceback.format_exc())
        box.exec()

    def pdf_done(self, path: str):
        self.last_dir = os.path.dirname(path)
        self.status(f"✔ PDF enregistré : {path}", 10000)
        if self.db.get_setting("open_pdf_after_export", "1") == "1":
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            box = QMessageBox(QMessageBox.Information, "PDF généré",
                              f"Le PDF a été enregistré :\n{path}", QMessageBox.Ok, self)
            open_btn = box.addButton("Ouvrir le PDF", QMessageBox.ActionRole)
            box.exec()
            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ---------------------------------------------------------------- #
    # Paramètres / devise
    # ---------------------------------------------------------------- #
    def _on_currency_changed(self):
        code = self.cb_currency.currentData()
        self.db.set_setting("currency", code)
        self.refresh_all()
        self.status(f"Devise d'affichage : {code} — {CURRENCIES[code][0]}")

    def edit_settings(self):
        dlg = SettingsDialog(self, self.db.all_settings())
        if dlg.exec():
            for k, v in dlg.get_data().items():
                self.db.set_setting(k, v)
            self.refresh_all()
            self.status("✔ Paramètres enregistrés")

    # ---------------------------------------------------------------- #
    # Export / import de la base
    # ---------------------------------------------------------------- #
    def export_db(self):
        default = os.path.join(self.last_dir, f"backup-production-{date.today().isoformat()}.json")
        json_filter = "Sauvegarde JSON (*.json)"
        db_filter = "Copie de la base SQLite (*.db)"
        path, chosen = QFileDialog.getSaveFileName(self, "Exporter la base de données", default,
                                                   f"{json_filter};;{db_filter}")
        if not path:
            return
        as_db = chosen == db_filter or path.lower().endswith(".db")
        if as_db and not path.lower().endswith(".db"):
            path = os.path.splitext(path)[0] + ".db"
        if not as_db and not path.lower().endswith(".json"):
            path += ".json"
        try:
            if as_db:
                self.db.export_db_copy(path)
                summary = "Copie complète de la base SQLite."
            else:
                counts = self.db.export_json(path)
                summary = self._counts_text(counts)
        except Exception as exc:
            self.error("Échec de l'export", exc)
            return
        self.last_dir = os.path.dirname(path)
        self.status(f"✔ Base exportée : {path}", 10000)
        QMessageBox.information(self, "Export réussi",
                                f"La base de données a été exportée vers :\n{path}\n\n{summary}")

    @staticmethod
    def _counts_text(counts: dict) -> str:
        labels = {"projects": "projet(s)", "invoices": "facture(s)", "expenses": "frais",
                  "allocations": "répartition(s)", "workers": "intervenant(s)",
                  "worker_roles": "barème(s)"}
        return " · ".join(f"{counts.get(k, 0)} {v}" for k, v in labels.items())

    def import_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une sauvegarde", self.last_dir,
            "Sauvegardes (*.json *.db);;Sauvegarde JSON (*.json);;Base SQLite (*.db)")
        if not path:
            return
        try:
            payload = Database.read_backup_file(path)
        except BackupValidationError as exc:
            box = QMessageBox(QMessageBox.Warning, "Fichier de sauvegarde invalide",
                              "Le fichier sélectionné ne respecte pas le schéma attendu. "
                              "Aucune donnée n'a été modifiée.", QMessageBox.Ok, self)
            box.setDetailedText("\n".join(exc.errors))
            box.exec()
            return
        except Exception as exc:
            self.error("Lecture impossible", exc)
            return
        counts = {t: len(v) for t, v in payload["data"].items()}
        when = payload.get("exported_at", "date inconnue")
        if not self.confirm(
                "Confirmer l'import",
                f"Sauvegarde : {os.path.basename(path)}\nExportée le : {when}\n\n"
                f"Contenu : {self._counts_text(counts)}\n\n"
                "Les données actuelles seront remplacées par celles de la sauvegarde.\n"
                "Cette action peut être annulée via « Annuler » (Ctrl+Z)."):
            return
        self.run(f"Import de la sauvegarde « {os.path.basename(path)} »",
                 self.db.restore_data, payload["data"])
        if not self.last_run_ok:
            return
        settings = payload.get("settings") or {}
        for key in ("company_name", "company_address", "currency"):
            if settings.get(key):
                self.db.set_setting(key, settings[key])
        self.cb_currency.blockSignals(True)
        self.cb_currency.setCurrentIndex(max(0, self.cb_currency.findData(self.currency)))
        self.cb_currency.blockSignals(False)
        self.last_dir = os.path.dirname(path)
        self.refresh_all()
        self.status(f"✔ Sauvegarde importée : {os.path.basename(path)} — Ctrl+Z pour annuler", 10000)

    def reset_demo(self):
        if self.confirm("Réinitialiser les données",
                        "Remplacer toutes les données actuelles par le jeu de démonstration ?\n\n"
                        "Cette action peut être annulée (Ctrl+Z)."):
            self.run("Réinitialisation avec les données de démonstration", self.db.load_demo_data)

    def clear_data(self):
        if self.confirm("Vider les données",
                        "Supprimer tous les projets, factures, frais, répartitions et "
                        "intervenants ?\n\nCette action peut être annulée (Ctrl+Z)."):
            self.run("Suppression de toutes les données", self.db.clear_all)

    def about(self):
        QMessageBox.about(
            self, "À propos",
            f"<h3>{APP_DISPLAY_NAME}</h3><p>Version {APP_VERSION}</p>"
            "<p>Gestion des projets, des factures clients, des frais de production et de leur "
            "répartition entre intervenants, avec rapports PDF.</p>"
            f"<p style='color:#64748B'>Base de données :<br>{self.db.path}</p>")

    def closeEvent(self, event):
        try:
            self.db.close()
        finally:
            event.accept()
