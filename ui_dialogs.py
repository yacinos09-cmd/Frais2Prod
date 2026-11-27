"""
Boîtes de dialogue de saisie (projets, factures, frais, travailleurs,
répartitions, paramètres) et composants d'interface réutilisables.
"""
from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QVBoxLayout, QWidget,
)

from utils import (
    DEFAULT_ROLES, EXPENSE_CATEGORIES, PROJECT_STATUSES, RATE_TYPES, allocation_amount,
    currency_decimals, format_money, format_rate, today_iso,
)

# --------------------------------------------------------------------------- #
# Composants utilitaires
# --------------------------------------------------------------------------- #

def repolish(widget: QWidget) -> None:
    """Réapplique la feuille de style après changement de propriété dynamique."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_kind(button: QPushButton, kind: str) -> QPushButton:
    button.setProperty("kind", kind)
    repolish(button)
    return button


def make_button(text: str, kind: str = "", tooltip: str = "", slot=None) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    if kind:
        btn.setProperty("kind", kind)
    if tooltip:
        btn.setToolTip(tooltip)
    if slot:
        btn.clicked.connect(slot)
    return btn


def money_spin(currency: str, maximum: float = 1e12) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(0, maximum)
    sp.setDecimals(currency_decimals(currency))
    sp.setGroupSeparatorShown(True)
    sp.setSuffix(f" {currency}")
    sp.setButtonSymbols(QDoubleSpinBox.NoButtons)
    sp.setAlignment(Qt.AlignRight)
    sp.setMinimumWidth(170)
    return sp


def percent_spin() -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(0, 100)
    sp.setDecimals(2)
    sp.setSuffix(" %")
    sp.setButtonSymbols(QDoubleSpinBox.NoButtons)
    sp.setAlignment(Qt.AlignRight)
    return sp


def date_edit(iso: str | None = None) -> QDateEdit:
    de = QDateEdit()
    de.setCalendarPopup(True)
    de.setDisplayFormat("dd/MM/yyyy")
    qd = QDate.fromString((iso or today_iso())[:10], "yyyy-MM-dd")
    de.setDate(qd if qd.isValid() else QDate.currentDate())
    return de


def iso_from(de: QDateEdit) -> str:
    return de.date().toString("yyyy-MM-dd")


def configure_table(table: QTableWidget, headers: list[str], stretch_col: int = 0,
                    fixed: dict[int, int] | None = None) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setWordWrap(False)
    hh = table.horizontalHeader()
    hh.setHighlightSections(False)
    hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    for i in range(len(headers)):
        hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
    for col, width in (fixed or {}).items():
        hh.setSectionResizeMode(col, QHeaderView.Interactive)
        table.setColumnWidth(col, width)
    if stretch_col is not None and 0 <= stretch_col < len(headers):
        hh.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    hh.setMinimumSectionSize(60)
    table.setTextElideMode(Qt.ElideRight)


class _BaseDialog(QDialog):
    def __init__(self, parent, title: str, subtitle: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(22, 20, 22, 18)
        self._root.setSpacing(12)
        t = QLabel(title)
        t.setObjectName("SectionTitle")
        self._root.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("Muted")
            s.setWordWrap(True)
            self._root.addWidget(s)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(10)
        self._root.addLayout(self.form)

    def add_buttons(self, ok_text: str = "Enregistrer"):
        self._root.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok = bb.button(QDialogButtonBox.Ok)
        ok.setText(ok_text)
        set_kind(ok, "primary")
        bb.button(QDialogButtonBox.Cancel).setText("Annuler")
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        self._root.addWidget(bb)
        self.ok_button = ok

    def _on_accept(self):
        if self.validate():
            self.accept()

    def validate(self) -> bool:
        return True

    def _require(self, widget: QLineEdit, label: str) -> bool:
        if not widget.text().strip():
            widget.setProperty("error", True)
            repolish(widget)
            widget.setFocus()
            QMessageBox.warning(self, "Champ obligatoire", f"Le champ « {label} » est obligatoire.")
            return False
        widget.setProperty("error", False)
        repolish(widget)
        return True


# --------------------------------------------------------------------------- #
# Projet
# --------------------------------------------------------------------------- #

class ProjectDialog(_BaseDialog):
    def __init__(self, parent, project: dict | None = None, clients: list[str] | None = None):
        super().__init__(parent, "Modifier le projet" if project else "Nouveau projet",
                         "Renseignez les informations générales du projet.")
        p = project or {}
        self.name = QLineEdit(p.get("name", ""))
        self.name.setPlaceholderText("Ex. : Spot TV – Lancement produit")
        self.client = QComboBox()
        self.client.setEditable(True)
        self.client.addItems(sorted(set(c for c in (clients or []) if c)))
        self.client.setCurrentText(p.get("client") or "")
        self.client.lineEdit().setPlaceholderText("Nom du client")
        self.date = date_edit(p.get("date"))
        self.status = QComboBox()
        self.status.addItems(PROJECT_STATUSES)
        if p.get("status"):
            if self.status.findText(p["status"]) < 0:
                self.status.addItem(p["status"])
            self.status.setCurrentText(p["status"])
        else:
            self.status.setCurrentText("En préparation")
        self.notes = QPlainTextEdit(p.get("notes") or "")
        self.notes.setFixedHeight(80)
        self.form.addRow("Nom du projet *", self.name)
        self.form.addRow("Client", self.client)
        self.form.addRow("Date", self.date)
        self.form.addRow("Statut", self.status)
        self.form.addRow("Notes", self.notes)
        self.add_buttons()

    def validate(self):
        return self._require(self.name, "Nom du projet")

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "client": self.client.currentText().strip() or None,
            "date": iso_from(self.date),
            "status": self.status.currentText(),
            "notes": self.notes.toPlainText().strip() or None,
        }


# --------------------------------------------------------------------------- #
# Facture client
# --------------------------------------------------------------------------- #

class InvoiceDialog(_BaseDialog):
    def __init__(self, parent, currency: str, project_name: str, invoice: dict | None = None,
                 suggested_ref: str = ""):
        super().__init__(parent, "Modifier la facture" if invoice else "Nouvelle facture payée",
                         f"Facture encaissée pour le projet « {project_name} ».")
        inv = invoice or {}
        self.reference = QLineEdit(inv.get("reference", suggested_ref))
        self.reference.setPlaceholderText("Ex. : FAC-2026-001")
        self.date = date_edit(inv.get("date"))
        self.amount = money_spin(currency)
        self.amount.setValue(float(inv.get("amount") or 0))
        self.notes = QPlainTextEdit(inv.get("notes") or "")
        self.notes.setFixedHeight(70)
        self.form.addRow("Référence *", self.reference)
        self.form.addRow("Date d'encaissement", self.date)
        self.form.addRow("Montant encaissé *", self.amount)
        self.form.addRow("Notes", self.notes)
        self.add_buttons()

    def validate(self):
        if not self._require(self.reference, "Référence"):
            return False
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Montant invalide", "Le montant encaissé doit être positif.")
            self.amount.setFocus()
            return False
        return True

    def get_data(self) -> dict:
        return {
            "reference": self.reference.text().strip(),
            "date": iso_from(self.date),
            "amount": self.amount.value(),
            "notes": self.notes.toPlainText().strip() or None,
        }


# --------------------------------------------------------------------------- #
# Frais de production
# --------------------------------------------------------------------------- #

class ExpenseDialog(_BaseDialog):
    def __init__(self, parent, currency: str, project_name: str, invoices: list[dict],
                 expense: dict | None = None, allocations: list[dict] | None = None):
        super().__init__(parent, "Modifier le frais" if expense else "Nouveau frais de production",
                         f"Frais rattaché au projet « {project_name} ». Il pourra ensuite être "
                         "réparti entre les intervenants.")
        self.currency = currency
        self.allocations = allocations or []
        e = expense or {}
        self.label = QLineEdit(e.get("label", ""))
        self.label.setPlaceholderText("Ex. : Journée de tournage")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(EXPENSE_CATEGORIES)
        self.category.setCurrentText(e.get("category") or "Tournage")
        self.date = date_edit(e.get("date"))
        self.amount = money_spin(currency)
        self.amount.setValue(float(e.get("amount") or 0))
        self.invoice = QComboBox()
        self.invoice.addItem("— Aucune facture associée —", None)
        for inv in invoices:
            self.invoice.addItem(f"{inv['reference']}  ({format_money(inv['amount'], currency)})",
                                 inv["id"])
        if e.get("invoice_id"):
            idx = self.invoice.findData(e["invoice_id"])
            if idx >= 0:
                self.invoice.setCurrentIndex(idx)
        self.notes = QPlainTextEdit(e.get("notes") or "")
        self.notes.setFixedHeight(70)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.form.addRow("Intitulé *", self.label)
        self.form.addRow("Catégorie", self.category)
        self.form.addRow("Date", self.date)
        self.form.addRow("Montant total *", self.amount)
        self.form.addRow("Facture client", self.invoice)
        self.form.addRow("Notes", self.notes)
        self.form.addRow("", self.hint)
        self.amount.valueChanged.connect(self._update_hint)
        self._update_hint()
        self.add_buttons()

    def _allocated_for(self, amount: float) -> float:
        return round(sum(allocation_amount(a["rate_type"], a["rate_value"], amount)
                         for a in self.allocations), 2)

    def _update_hint(self):
        if not self.allocations:
            self.hint.setText("")
            return
        amount = self.amount.value()
        alloc = self._allocated_for(amount)
        rest = amount - alloc
        color = "#DC2626" if rest < -0.005 else "#15803D"
        msg = (f"Déjà réparti avec ce montant : <b>{format_money(alloc, self.currency)}</b> — "
               f"reste : <b style='color:{color}'>{format_money(rest, self.currency)}</b>")
        if rest < -0.005:
            msg += "<br><span style='color:#DC2626'>⚠ Le montant est inférieur au total déjà réparti.</span>"
        self.hint.setText(msg)

    def validate(self):
        if not self._require(self.label, "Intitulé"):
            return False
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Montant invalide", "Le montant du frais doit être positif.")
            self.amount.setFocus()
            return False
        if self.allocations and self._allocated_for(self.amount.value()) > self.amount.value() + 0.005:
            r = QMessageBox.question(
                self, "Répartition dépassée",
                "Avec ce montant, la répartition existante dépasse le total du frais.\n"
                "Voulez-vous enregistrer quand même ?")
            return r == QMessageBox.Yes
        return True

    def get_data(self) -> dict:
        return {
            "label": self.label.text().strip(),
            "category": self.category.currentText().strip() or None,
            "date": iso_from(self.date),
            "amount": self.amount.value(),
            "invoice_id": self.invoice.currentData(),
            "notes": self.notes.toPlainText().strip() or None,
        }


# --------------------------------------------------------------------------- #
# Travailleur & barèmes
# --------------------------------------------------------------------------- #

class WorkerDialog(_BaseDialog):
    COL_ROLE, COL_TYPE, COL_VALUE = range(3)

    def __init__(self, parent, currency: str, worker: dict | None = None,
                 role_suggestions: list[str] | None = None):
        super().__init__(parent, "Modifier l'intervenant" if worker else "Nouvel intervenant",
                         "Un intervenant peut exercer plusieurs métiers, chacun avec son barème "
                         "par défaut (montant fixe ou pourcentage du frais).")
        self.setMinimumWidth(700)
        self.currency = currency
        self.role_suggestions = sorted(set(DEFAULT_ROLES) | set(role_suggestions or []),
                                       key=str.lower)
        w = worker or {}
        self.name = QLineEdit(w.get("name", ""))
        self.name.setPlaceholderText("Prénom Nom")
        self.email = QLineEdit(w.get("email") or "")
        self.email.setPlaceholderText("adresse@email.com")
        self.phone = QLineEdit(w.get("phone") or "")
        self.notes = QLineEdit(w.get("notes") or "")
        self.form.addRow("Nom complet *", self.name)
        self.form.addRow("E-mail", self.email)
        self.form.addRow("Téléphone", self.phone)
        self.form.addRow("Notes", self.notes)

        lbl = QLabel("Métiers & barèmes de paiement")
        lbl.setObjectName("SectionTitle")
        self._root.addWidget(lbl)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Métier / rôle", "Type de barème", "Valeur par défaut"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 190)
        self.table.setMinimumHeight(170)
        self._root.addWidget(self.table)

        row = QHBoxLayout()
        row.addWidget(make_button("＋ Ajouter un métier", slot=lambda: self.add_role_row()))
        row.addWidget(make_button("Retirer le métier sélectionné", kind="danger",
                                  slot=self.remove_role_row))
        row.addStretch(1)
        self._root.addLayout(row)

        for r in w.get("roles", []):
            self.add_role_row(r["role"], r["rate_type"], r["rate_value"])
        if not w.get("roles"):
            self.add_role_row()
        self.add_buttons()

    def add_role_row(self, role: str = "", rate_type: str = "fixed", rate_value: float = 0.0):
        r = self.table.rowCount()
        self.table.insertRow(r)
        cb_role = QComboBox()
        cb_role.setEditable(True)
        cb_role.addItems(self.role_suggestions)
        cb_role.setCurrentText(role)
        cb_role.lineEdit().setPlaceholderText("Choisir ou saisir un métier")
        cb_type = QComboBox()
        for key, label in RATE_TYPES.items():
            cb_type.addItem(label, key)
        cb_type.setCurrentIndex(cb_type.findData(rate_type))
        cb_type.setMinimumWidth(165)
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        sp_fixed = money_spin(self.currency)
        sp_pct = percent_spin()
        sp_fixed.setMinimumWidth(0)
        lay.addWidget(sp_fixed)
        lay.addWidget(sp_pct)
        if rate_type == "percent":
            sp_pct.setValue(float(rate_value))
        else:
            sp_fixed.setValue(float(rate_value))

        def sync():
            is_pct = cb_type.currentData() == "percent"
            sp_pct.setVisible(is_pct)
            sp_fixed.setVisible(not is_pct)
        cb_type.currentIndexChanged.connect(sync)
        sync()
        container.sp_fixed = sp_fixed
        container.sp_pct = sp_pct
        self.table.setCellWidget(r, self.COL_ROLE, cb_role)
        self.table.setCellWidget(r, self.COL_TYPE, cb_type)
        self.table.setCellWidget(r, self.COL_VALUE, container)
        if not role:
            cb_role.setFocus()

    def remove_role_row(self):
        r = self.table.currentRow()
        if r < 0:
            r = self.table.rowCount() - 1
        if r >= 0:
            self.table.removeRow(r)

    def get_roles(self) -> list[dict]:
        roles = []
        for r in range(self.table.rowCount()):
            role = self.table.cellWidget(r, self.COL_ROLE).currentText().strip()
            if not role:
                continue
            rtype = self.table.cellWidget(r, self.COL_TYPE).currentData()
            box = self.table.cellWidget(r, self.COL_VALUE)
            value = box.sp_pct.value() if rtype == "percent" else box.sp_fixed.value()
            roles.append({"role": role, "rate_type": rtype, "rate_value": value})
        return roles

    def validate(self):
        if not self._require(self.name, "Nom complet"):
            return False
        roles = self.get_roles()
        if not roles:
            QMessageBox.warning(self, "Métier requis",
                                "Ajoutez au moins un métier avec son barème.")
            return False
        names = [r["role"].lower() for r in roles]
        if len(names) != len(set(names)):
            QMessageBox.warning(self, "Doublon", "Un même métier est saisi plusieurs fois.")
            return False
        return True

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "email": self.email.text().strip() or None,
            "phone": self.phone.text().strip() or None,
            "notes": self.notes.text().strip() or None,
        }


# --------------------------------------------------------------------------- #
# Répartition d'un frais
# --------------------------------------------------------------------------- #

class AllocationDialog(_BaseDialog):
    """Affecte une part d'un frais à un intervenant, avec calcul en temps réel."""

    def __init__(self, parent, db, currency: str, expense: dict, allocation: dict | None = None):
        super().__init__(parent,
                         "Modifier la répartition" if allocation else "Répartir vers un intervenant",
                         f"Frais « {expense['label']} » — montant total "
                         f"{format_money(expense['amount'], currency)}")
        self.setMinimumWidth(560)
        self.db = db
        self.currency = currency
        self.expense = expense
        self.allocation = allocation
        self.workers = db.list_workers()
        self.other_allocated = db.allocated_total(
            expense["id"], expense["amount"],
            exclude_allocation_id=allocation["id"] if allocation else None)

        self.worker = QComboBox()
        self.worker.setEditable(True)
        self.worker.setInsertPolicy(QComboBox.NoInsert)
        self.worker.completer().setFilterMode(Qt.MatchContains)
        self.worker.completer().setCompletionMode(self.worker.completer().CompletionMode.PopupCompletion)
        for w in self.workers:
            roles = ", ".join(r["role"] for r in w["roles"])
            self.worker.addItem(f"{w['name']}" + (f"  —  {roles}" if roles else ""), w["id"])
        self.role = QComboBox()
        self.role.setEditable(True)
        self.rate_type = QComboBox()
        for key, label in RATE_TYPES.items():
            self.rate_type.addItem(label, key)
        self.value_fixed = money_spin(currency)
        self.value_pct = percent_spin()
        value_box = QHBoxLayout()
        value_box.setContentsMargins(0, 0, 0, 0)
        value_box.addWidget(self.value_fixed, 1)
        value_box.addWidget(self.value_pct, 1)
        self.btn_rest = make_button("Attribuer le reste",
                                    tooltip="Affecte exactement le montant restant à répartir",
                                    slot=self._assign_rest)
        value_box.addWidget(self.btn_rest)
        self.barem_hint = QLabel()
        self.barem_hint.setObjectName("Muted")
        self.notes = QLineEdit(allocation.get("notes") or "" if allocation else "")
        self.notes.setPlaceholderText("Optionnel (ex. : 2 jours, version EN…)")

        self.form.addRow("Intervenant *", self.worker)
        self.form.addRow("Métier", self.role)
        self.form.addRow("Barème", self.rate_type)
        self.form.addRow("Valeur", value_box)
        self.form.addRow("", self.barem_hint)
        self.form.addRow("Note", self.notes)

        # Panneau de calcul en temps réel
        panel = QFrame()
        panel.setObjectName("Card")
        grid = QGridLayout(panel)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(18)
        self.lbl_total = QLabel()
        self.lbl_other = QLabel()
        self.lbl_this = QLabel()
        self.lbl_rest = QLabel()
        self.lbl_rest.setObjectName("Pill")
        for i, (title, w) in enumerate([("Montant du frais", self.lbl_total),
                                        ("Déjà réparti", self.lbl_other),
                                        ("Cette part", self.lbl_this),
                                        ("Reste à répartir", self.lbl_rest)]):
            t = QLabel(title.upper())
            t.setObjectName("KpiTitle")
            grid.addWidget(t, 0, i)
            grid.addWidget(w, 1, i)
        self._root.addWidget(panel)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        self._root.addWidget(self.warning)

        # Signaux
        self.worker.currentIndexChanged.connect(self._on_worker_changed)
        self.role.currentTextChanged.connect(self._on_role_changed)
        self.rate_type.currentIndexChanged.connect(self._on_type_changed)
        self.value_fixed.valueChanged.connect(self._recompute)
        self.value_pct.valueChanged.connect(self._recompute)

        # Valeurs initiales
        if allocation:
            idx = self.worker.findData(allocation["worker_id"])
            self.worker.blockSignals(True)
            self.worker.setCurrentIndex(max(idx, 0))
            self.worker.blockSignals(False)
            self._fill_roles(prefill=False)
            self.role.blockSignals(True)
            self.role.setCurrentText(allocation.get("role") or "")
            self.role.blockSignals(False)
            self.rate_type.setCurrentIndex(self.rate_type.findData(allocation["rate_type"]))
            if allocation["rate_type"] == "percent":
                self.value_pct.setValue(allocation["rate_value"])
            else:
                self.value_fixed.setValue(allocation["rate_value"])
            self._update_barem_hint()
        else:
            self._on_worker_changed()
        self._on_type_changed()
        self.add_buttons("Enregistrer la répartition")
        self._recompute()

    # -- helpers --------------------------------------------------------- #
    def _current_worker(self) -> dict | None:
        wid = self.worker.currentData()
        return next((w for w in self.workers if w["id"] == wid), None)

    def _fill_roles(self, prefill: bool = True):
        w = self._current_worker()
        self.role.blockSignals(True)
        self.role.clear()
        if w:
            for r in w["roles"]:
                self.role.addItem(r["role"])
        self.role.blockSignals(False)
        if prefill:
            self._on_role_changed(self.role.currentText())

    def _barem_for(self, role: str) -> dict | None:
        w = self._current_worker()
        if not w:
            return None
        return next((r for r in w["roles"] if r["role"].lower() == (role or "").lower()), None)

    def _on_worker_changed(self, *_):
        self._fill_roles(prefill=True)

    def _on_role_changed(self, role: str):
        b = self._barem_for(role)
        if b:  # pré-remplissage automatique du barème par défaut
            self.rate_type.blockSignals(True)
            self.rate_type.setCurrentIndex(self.rate_type.findData(b["rate_type"]))
            self.rate_type.blockSignals(False)
            if b["rate_type"] == "percent":
                self.value_pct.setValue(b["rate_value"])
            else:
                self.value_fixed.setValue(b["rate_value"])
            self._on_type_changed()
        self._update_barem_hint()

    def _update_barem_hint(self):
        b = self._barem_for(self.role.currentText())
        if b:
            self.barem_hint.setText("Barème par défaut de ce métier : "
                                    + format_rate(b["rate_type"], b["rate_value"], self.currency)
                                    + " (modifiable pour ce frais)")
        else:
            self.barem_hint.setText("Aucun barème par défaut pour ce métier.")

    def _on_type_changed(self, *_):
        is_pct = self.rate_type.currentData() == "percent"
        self.value_pct.setVisible(is_pct)
        self.value_fixed.setVisible(not is_pct)
        self._recompute()

    def _assign_rest(self):
        rest = max(0.0, self.expense["amount"] - self.other_allocated)
        if self.rate_type.currentData() == "percent" and self.expense["amount"] > 0:
            self.value_pct.setValue(rest / self.expense["amount"] * 100)
        else:
            self.rate_type.setCurrentIndex(self.rate_type.findData("fixed"))
            self.value_fixed.setValue(rest)

    def _value(self) -> float:
        return (self.value_pct.value() if self.rate_type.currentData() == "percent"
                else self.value_fixed.value())

    def this_amount(self) -> float:
        return allocation_amount(self.rate_type.currentData(), self._value(), self.expense["amount"])

    def _recompute(self, *_):
        if not hasattr(self, "lbl_rest"):
            return
        m = lambda v: format_money(v, self.currency)  # noqa: E731
        this = self.this_amount()
        rest = round(self.expense["amount"] - self.other_allocated - this, 2)
        self.lbl_total.setText(f"<b>{m(self.expense['amount'])}</b>")
        self.lbl_other.setText(m(self.other_allocated))
        self.lbl_this.setText(f"<b>{m(this)}</b>")
        self.lbl_rest.setText(m(rest))
        state = "error" if rest < -0.005 else ("ok" if abs(rest) < 0.005 else "warn")
        self.lbl_rest.setProperty("state", state)
        repolish(self.lbl_rest)
        if rest < -0.005:
            self.warning.setText(f"<span style='color:#DC2626'><b>⚠ Dépassement :</b> la "
                                 f"répartition excède le montant disponible de {m(-rest)}.</span>")
        else:
            self.warning.setText("")

    def validate(self):
        if self._current_worker() is None:
            QMessageBox.warning(self, "Intervenant requis",
                                "Sélectionnez un intervenant dans la liste.")
            return False
        if self.this_amount() <= 0:
            QMessageBox.warning(self, "Montant nul", "Le montant attribué doit être positif.")
            return False
        rest = self.expense["amount"] - self.other_allocated - self.this_amount()
        if rest < -0.005:
            r = QMessageBox.question(
                self, "Dépassement du montant disponible",
                f"Cette répartition dépasse le montant du frais de "
                f"{format_money(-rest, self.currency)}.\n\nEnregistrer quand même ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            return r == QMessageBox.Yes
        return True

    def get_data(self) -> dict:
        return {
            "expense_id": self.expense["id"],
            "worker_id": self.worker.currentData(),
            "role": self.role.currentText().strip() or None,
            "rate_type": self.rate_type.currentData(),
            "rate_value": self._value(),
            "notes": self.notes.text().strip() or None,
        }

    def worker_name(self) -> str:
        w = self._current_worker()
        return w["name"] if w else ""


# --------------------------------------------------------------------------- #
# Paramètres de la société
# --------------------------------------------------------------------------- #

class SettingsDialog(_BaseDialog):
    def __init__(self, parent, settings: dict):
        super().__init__(parent, "Paramètres de la société",
                         "Ces informations apparaissent en en-tête des rapports PDF.")
        self.company = QLineEdit(settings.get("company_name", ""))
        self.address = QPlainTextEdit(settings.get("company_address", ""))
        self.address.setFixedHeight(70)
        self.address.setPlaceholderText("Adresse, téléphone, e-mail, NIF…")
        self.open_pdf = QCheckBox("Ouvrir automatiquement les PDF après génération")
        self.open_pdf.setChecked(settings.get("open_pdf_after_export", "1") == "1")
        self.form.addRow("Nom de la société *", self.company)
        self.form.addRow("Coordonnées", self.address)
        self.form.addRow("", self.open_pdf)
        self.add_buttons()

    def validate(self):
        return self._require(self.company, "Nom de la société")

    def get_data(self) -> dict:
        return {
            "company_name": self.company.text().strip(),
            "company_address": self.address.toPlainText().strip(),
            "open_pdf_after_export": "1" if self.open_pdf.isChecked() else "0",
        }
