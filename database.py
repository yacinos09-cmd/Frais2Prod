"""
Couche d'accès aux données (SQLite).

Toutes les opérations d'écriture passent par des méthodes transactionnelles.
Les méthodes ``dump_data`` / ``restore_data`` servent à la fois aux
instantanés d'historique (Annuler / Rétablir) et à l'export / import JSON.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import APP_VERSION, allocation_amount

BACKUP_FORMAT = "gestion-production-backup"
SCHEMA_VERSION = 1

# Ordre d'insertion (respecte les clés étrangères)
TABLES: list[str] = [
    "workers",
    "worker_roles",
    "projects",
    "invoices",
    "expenses",
    "allocations",
]

# Colonnes : (nom, type python attendu, obligatoire, nullable)
COLUMNS: dict[str, list[tuple[str, tuple, bool, bool]]] = {
    "workers": [
        ("id", (int,), True, False),
        ("name", (str,), True, False),
        ("email", (str,), False, True),
        ("phone", (str,), False, True),
        ("notes", (str,), False, True),
    ],
    "worker_roles": [
        ("id", (int,), True, False),
        ("worker_id", (int,), True, False),
        ("role", (str,), True, False),
        ("rate_type", (str,), True, False),
        ("rate_value", (int, float), True, False),
    ],
    "projects": [
        ("id", (int,), True, False),
        ("name", (str,), True, False),
        ("client", (str,), False, True),
        ("date", (str,), False, True),
        ("status", (str,), False, True),
        ("notes", (str,), False, True),
    ],
    "invoices": [
        ("id", (int,), True, False),
        ("project_id", (int,), True, False),
        ("reference", (str,), True, False),
        ("date", (str,), False, True),
        ("amount", (int, float), True, False),
        ("notes", (str,), False, True),
    ],
    "expenses": [
        ("id", (int,), True, False),
        ("project_id", (int,), True, False),
        ("invoice_id", (int,), False, True),
        ("label", (str,), True, False),
        ("category", (str,), False, True),
        ("date", (str,), False, True),
        ("amount", (int, float), True, False),
        ("notes", (str,), False, True),
    ],
    "allocations": [
        ("id", (int,), True, False),
        ("expense_id", (int,), True, False),
        ("worker_id", (int,), True, False),
        ("role", (str,), False, True),
        ("rate_type", (str,), True, False),
        ("rate_value", (int, float), True, False),
        ("notes", (str,), False, True),
    ],
}

# Références (table, colonne) -> table cible
FOREIGN_KEYS = {
    ("worker_roles", "worker_id"): "workers",
    ("invoices", "project_id"): "projects",
    ("expenses", "project_id"): "projects",
    ("expenses", "invoice_id"): "invoices",
    ("allocations", "expense_id"): "expenses",
    ("allocations", "worker_id"): "workers",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS workers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS worker_roles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id  INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    rate_type  TEXT NOT NULL CHECK (rate_type IN ('fixed', 'percent')),
    rate_value REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS projects (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL,
    client TEXT,
    date   TEXT,
    status TEXT,
    notes  TEXT
);
CREATE TABLE IF NOT EXISTS invoices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    reference  TEXT NOT NULL,
    date       TEXT,
    amount     REAL NOT NULL DEFAULT 0,
    notes      TEXT
);
CREATE TABLE IF NOT EXISTS expenses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    label      TEXT NOT NULL,
    category   TEXT,
    date       TEXT,
    amount     REAL NOT NULL DEFAULT 0,
    notes      TEXT
);
CREATE TABLE IF NOT EXISTS allocations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_id INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    worker_id  INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    role       TEXT,
    rate_type  TEXT NOT NULL CHECK (rate_type IN ('fixed', 'percent')),
    rate_value REAL NOT NULL DEFAULT 0,
    notes      TEXT
);
CREATE INDEX IF NOT EXISTS idx_roles_worker      ON worker_roles(worker_id);
CREATE INDEX IF NOT EXISTS idx_invoices_project  ON invoices(project_id);
CREATE INDEX IF NOT EXISTS idx_expenses_project  ON expenses(project_id);
CREATE INDEX IF NOT EXISTS idx_alloc_expense     ON allocations(expense_id);
CREATE INDEX IF NOT EXISTS idx_alloc_worker      ON allocations(worker_id);
"""

DEFAULT_SETTINGS = {
    "company_name": "Ma Société de Production",
    "company_address": "",
    "currency": "FDJ",
    "open_pdf_after_export": "1",
    "schema_version": str(SCHEMA_VERSION),
}


class BackupValidationError(ValueError):
    """Le fichier de sauvegarde ne respecte pas le schéma attendu."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors[:20]))


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.is_new = not Path(self.path).exists() or Path(self.path).stat().st_size == 0
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA_SQL)
        for key, value in DEFAULT_SETTINGS.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value)
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ #
    # Outils
    # ------------------------------------------------------------------ #
    @contextmanager
    def transaction(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _rows(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _row(self, sql: str, params: tuple = ()) -> dict | None:
        r = self.conn.execute(sql, params).fetchone()
        return dict(r) if r else None

    # ------------------------------------------------------------------ #
    # Paramètres
    # ------------------------------------------------------------------ #
    def get_setting(self, key: str, default: str = "") -> str:
        r = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return r["value"] if r and r["value"] is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def all_settings(self) -> dict:
        return {r["key"]: r["value"] for r in self._rows("SELECT key, value FROM settings")}

    # ------------------------------------------------------------------ #
    # Travailleurs & barèmes
    # ------------------------------------------------------------------ #
    def list_workers(self) -> list[dict]:
        workers = self._rows("SELECT * FROM workers ORDER BY name COLLATE NOCASE")
        roles = self._rows("SELECT * FROM worker_roles ORDER BY id")
        by_worker: dict[int, list[dict]] = {}
        for r in roles:
            by_worker.setdefault(r["worker_id"], []).append(r)
        stats = {
            r["worker_id"]: r
            for r in self._rows(
                """
                SELECT a.worker_id,
                       COUNT(DISTINCT e.project_id) AS nb_projects,
                       COUNT(a.id) AS nb_allocations
                FROM allocations a JOIN expenses e ON e.id = a.expense_id
                GROUP BY a.worker_id
                """
            )
        }
        earnings = self._earnings_by_worker()
        for w in workers:
            w["roles"] = by_worker.get(w["id"], [])
            s = stats.get(w["id"], {})
            w["nb_projects"] = s.get("nb_projects", 0)
            w["nb_allocations"] = s.get("nb_allocations", 0)
            w["total_earned"] = earnings.get(w["id"], 0.0)
        return workers

    def get_worker(self, worker_id: int) -> dict | None:
        w = self._row("SELECT * FROM workers WHERE id = ?", (worker_id,))
        if w:
            w["roles"] = self._rows(
                "SELECT * FROM worker_roles WHERE worker_id = ? ORDER BY id", (worker_id,)
            )
        return w

    def _write_roles(self, c, worker_id: int, roles: list[dict]) -> None:
        c.execute("DELETE FROM worker_roles WHERE worker_id = ?", (worker_id,))
        for r in roles:
            c.execute(
                "INSERT INTO worker_roles(worker_id, role, rate_type, rate_value) "
                "VALUES (?, ?, ?, ?)",
                (worker_id, r["role"].strip(), r["rate_type"], float(r["rate_value"])),
            )

    def add_worker(self, data: dict, roles: list[dict]) -> int:
        with self.transaction() as c:
            cur = c.execute(
                "INSERT INTO workers(name, email, phone, notes) VALUES (?, ?, ?, ?)",
                (data["name"].strip(), data.get("email"), data.get("phone"), data.get("notes")),
            )
            wid = cur.lastrowid
            self._write_roles(c, wid, roles)
            return wid

    def update_worker(self, worker_id: int, data: dict, roles: list[dict]) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE workers SET name = ?, email = ?, phone = ?, notes = ? WHERE id = ?",
                (data["name"].strip(), data.get("email"), data.get("phone"),
                 data.get("notes"), worker_id),
            )
            self._write_roles(c, worker_id, roles)

    def delete_worker(self, worker_id: int) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM workers WHERE id = ?", (worker_id,))

    def count_worker_allocations(self, worker_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM allocations WHERE worker_id = ?", (worker_id,)
        ).fetchone()[0]

    def all_role_names(self) -> list[str]:
        return [r["role"] for r in self._rows(
            "SELECT DISTINCT role FROM worker_roles ORDER BY role COLLATE NOCASE")]

    # ------------------------------------------------------------------ #
    # Projets
    # ------------------------------------------------------------------ #
    def list_projects(self) -> list[dict]:
        projects = self._rows(
            "SELECT * FROM projects ORDER BY COALESCE(date, '') DESC, name COLLATE NOCASE"
        )
        inv = {r["project_id"]: r["t"] for r in self._rows(
            "SELECT project_id, SUM(amount) AS t FROM invoices GROUP BY project_id")}
        exp = {r["project_id"]: r["t"] for r in self._rows(
            "SELECT project_id, SUM(amount) AS t FROM expenses GROUP BY project_id")}
        alloc = self._allocated_by_project()
        for p in projects:
            p["total_invoiced"] = inv.get(p["id"]) or 0.0
            p["total_expenses"] = exp.get(p["id"]) or 0.0
            p["total_allocated"] = alloc.get(p["id"], 0.0)
            p["margin"] = p["total_invoiced"] - p["total_expenses"]
        return projects

    def get_project(self, project_id: int) -> dict | None:
        return self._row("SELECT * FROM projects WHERE id = ?", (project_id,))

    def add_project(self, data: dict) -> int:
        with self.transaction() as c:
            cur = c.execute(
                "INSERT INTO projects(name, client, date, status, notes) VALUES (?, ?, ?, ?, ?)",
                (data["name"].strip(), data.get("client"), data.get("date"),
                 data.get("status"), data.get("notes")),
            )
            return cur.lastrowid

    def update_project(self, project_id: int, data: dict) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE projects SET name = ?, client = ?, date = ?, status = ?, notes = ? "
                "WHERE id = ?",
                (data["name"].strip(), data.get("client"), data.get("date"),
                 data.get("status"), data.get("notes"), project_id),
            )

    def delete_project(self, project_id: int) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # ------------------------------------------------------------------ #
    # Factures clients
    # ------------------------------------------------------------------ #
    def list_invoices(self, project_id: int) -> list[dict]:
        return self._rows(
            "SELECT * FROM invoices WHERE project_id = ? ORDER BY COALESCE(date, ''), id",
            (project_id,),
        )

    def get_invoice(self, invoice_id: int) -> dict | None:
        return self._row("SELECT * FROM invoices WHERE id = ?", (invoice_id,))

    def add_invoice(self, data: dict) -> int:
        with self.transaction() as c:
            cur = c.execute(
                "INSERT INTO invoices(project_id, reference, date, amount, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (data["project_id"], data["reference"].strip(), data.get("date"),
                 float(data["amount"]), data.get("notes")),
            )
            return cur.lastrowid

    def update_invoice(self, invoice_id: int, data: dict) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE invoices SET reference = ?, date = ?, amount = ?, notes = ? WHERE id = ?",
                (data["reference"].strip(), data.get("date"), float(data["amount"]),
                 data.get("notes"), invoice_id),
            )

    def delete_invoice(self, invoice_id: int) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))

    # ------------------------------------------------------------------ #
    # Frais de production
    # ------------------------------------------------------------------ #
    def list_expenses(self, project_id: int) -> list[dict]:
        expenses = self._rows(
            """
            SELECT e.*, i.reference AS invoice_reference
            FROM expenses e LEFT JOIN invoices i ON i.id = e.invoice_id
            WHERE e.project_id = ?
            ORDER BY COALESCE(e.date, ''), e.id
            """,
            (project_id,),
        )
        for e in expenses:
            e["allocated"] = self.allocated_total(e["id"], e["amount"])
            e["remaining"] = round(e["amount"] - e["allocated"], 2)
        return expenses

    def get_expense(self, expense_id: int) -> dict | None:
        e = self._row(
            """
            SELECT e.*, i.reference AS invoice_reference, i.amount AS invoice_amount,
                   i.date AS invoice_date, p.name AS project_name, p.client AS project_client
            FROM expenses e
            JOIN projects p ON p.id = e.project_id
            LEFT JOIN invoices i ON i.id = e.invoice_id
            WHERE e.id = ?
            """,
            (expense_id,),
        )
        if e:
            e["allocated"] = self.allocated_total(e["id"], e["amount"])
            e["remaining"] = round(e["amount"] - e["allocated"], 2)
        return e

    def add_expense(self, data: dict) -> int:
        with self.transaction() as c:
            cur = c.execute(
                "INSERT INTO expenses(project_id, invoice_id, label, category, date, amount, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data["project_id"], data.get("invoice_id"), data["label"].strip(),
                 data.get("category"), data.get("date"), float(data["amount"]),
                 data.get("notes")),
            )
            return cur.lastrowid

    def update_expense(self, expense_id: int, data: dict) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE expenses SET invoice_id = ?, label = ?, category = ?, date = ?, "
                "amount = ?, notes = ? WHERE id = ?",
                (data.get("invoice_id"), data["label"].strip(), data.get("category"),
                 data.get("date"), float(data["amount"]), data.get("notes"), expense_id),
            )

    def delete_expense(self, expense_id: int) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    # ------------------------------------------------------------------ #
    # Répartitions
    # ------------------------------------------------------------------ #
    def list_allocations(self, expense_id: int) -> list[dict]:
        rows = self._rows(
            """
            SELECT a.*, w.name AS worker_name, e.amount AS expense_amount
            FROM allocations a
            JOIN workers w ON w.id = a.worker_id
            JOIN expenses e ON e.id = a.expense_id
            WHERE a.expense_id = ?
            ORDER BY a.id
            """,
            (expense_id,),
        )
        for r in rows:
            r["amount"] = allocation_amount(r["rate_type"], r["rate_value"], r["expense_amount"])
        return rows

    def allocated_total(self, expense_id: int, expense_amount: float | None = None,
                        exclude_allocation_id: int | None = None) -> float:
        if expense_amount is None:
            r = self.conn.execute("SELECT amount FROM expenses WHERE id = ?", (expense_id,)).fetchone()
            expense_amount = r["amount"] if r else 0.0
        total = 0.0
        for a in self._rows(
            "SELECT id, rate_type, rate_value FROM allocations WHERE expense_id = ?", (expense_id,)
        ):
            if exclude_allocation_id is not None and a["id"] == exclude_allocation_id:
                continue
            total += allocation_amount(a["rate_type"], a["rate_value"], expense_amount)
        return round(total, 2)

    def add_allocation(self, data: dict) -> int:
        with self.transaction() as c:
            cur = c.execute(
                "INSERT INTO allocations(expense_id, worker_id, role, rate_type, rate_value, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (data["expense_id"], data["worker_id"], data.get("role"),
                 data["rate_type"], float(data["rate_value"]), data.get("notes")),
            )
            return cur.lastrowid

    def update_allocation(self, allocation_id: int, data: dict) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE allocations SET worker_id = ?, role = ?, rate_type = ?, rate_value = ?, "
                "notes = ? WHERE id = ?",
                (data["worker_id"], data.get("role"), data["rate_type"],
                 float(data["rate_value"]), data.get("notes"), allocation_id),
            )

    def delete_allocation(self, allocation_id: int) -> None:
        with self.transaction() as c:
            c.execute("DELETE FROM allocations WHERE id = ?", (allocation_id,))

    # ------------------------------------------------------------------ #
    # Agrégats / rapports
    # ------------------------------------------------------------------ #
    def _allocation_lines(self, project_id: int | None = None) -> list[dict]:
        sql = """
            SELECT a.id, a.worker_id, a.role, a.rate_type, a.rate_value,
                   e.id AS expense_id, e.label AS expense_label, e.category,
                   e.amount AS expense_amount, e.date AS expense_date,
                   p.id AS project_id, p.name AS project_name, p.client AS project_client,
                   p.date AS project_date
            FROM allocations a
            JOIN expenses e ON e.id = a.expense_id
            JOIN projects p ON p.id = e.project_id
        """
        params: tuple = ()
        if project_id is not None:
            sql += " WHERE p.id = ?"
            params = (project_id,)
        sql += " ORDER BY COALESCE(p.date, ''), p.name, e.id, a.id"
        rows = self._rows(sql, params)
        for r in rows:
            r["amount"] = allocation_amount(r["rate_type"], r["rate_value"], r["expense_amount"])
        return rows

    def _earnings_by_worker(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for r in self._allocation_lines():
            out[r["worker_id"]] = round(out.get(r["worker_id"], 0.0) + r["amount"], 2)
        return out

    def _allocated_by_project(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for r in self._allocation_lines():
            out[r["project_id"]] = round(out.get(r["project_id"], 0.0) + r["amount"], 2)
        return out

    def worker_earnings_report(self, project_id: int | None = None) -> list[dict]:
        """Gains consolidés par intervenant (filtrable par projet)."""
        lines = self._allocation_lines(project_id)
        workers = {w["id"]: w for w in self.list_workers()}
        report: dict[int, dict] = {}
        for line in lines:
            w = workers.get(line["worker_id"])
            if not w:
                continue
            entry = report.setdefault(line["worker_id"], {
                "worker_id": w["id"],
                "name": w["name"],
                "roles": [r["role"] for r in w["roles"]],
                "lines": [],
                "total": 0.0,
                "projects": set(),
            })
            entry["lines"].append(line)
            entry["total"] = round(entry["total"] + line["amount"], 2)
            entry["projects"].add(line["project_id"])
        result = []
        for entry in report.values():
            entry["nb_projects"] = len(entry.pop("projects"))
            result.append(entry)
        result.sort(key=lambda e: (-e["total"], e["name"].lower()))
        return result

    def dashboard_stats(self) -> dict:
        c = self.conn
        total_invoiced = c.execute("SELECT COALESCE(SUM(amount), 0) FROM invoices").fetchone()[0]
        total_expenses = c.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
        total_allocated = round(sum(self._earnings_by_worker().values()), 2)
        by_status = {r["status"] or "—": r["n"] for r in self._rows(
            "SELECT status, COUNT(*) AS n FROM projects GROUP BY status")}
        return {
            "total_invoiced": total_invoiced,
            "total_expenses": total_expenses,
            "total_allocated": total_allocated,
            "remaining": round(total_expenses - total_allocated, 2),
            "margin": round(total_invoiced - total_expenses, 2),
            "nb_projects": c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "nb_workers": c.execute("SELECT COUNT(*) FROM workers").fetchone()[0],
            "nb_expenses": c.execute("SELECT COUNT(*) FROM expenses").fetchone()[0],
            "by_status": by_status,
        }

    # ------------------------------------------------------------------ #
    # Instantanés (historique) et sauvegardes
    # ------------------------------------------------------------------ #
    def dump_data(self) -> dict[str, list[dict]]:
        data = {}
        for table in TABLES:
            cols = ", ".join(c[0] for c in COLUMNS[table])
            data[table] = self._rows(f"SELECT {cols} FROM {table} ORDER BY id")
        return data

    def restore_data(self, data: dict[str, list[dict]]) -> None:
        """Remplace intégralement les données par celles fournies (transactionnel)."""
        with self.transaction() as c:
            for table in reversed(TABLES):
                c.execute(f"DELETE FROM {table}")
            c.execute(
                "DELETE FROM sqlite_sequence WHERE name IN (%s)" % ",".join("?" * len(TABLES)),
                TABLES,
            )
            for table in TABLES:
                cols = [col[0] for col in COLUMNS[table]]
                sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
                       f"VALUES ({', '.join('?' * len(cols))})")
                c.executemany(sql, [tuple(row.get(col) for col in cols)
                                    for row in data.get(table, [])])

    def clear_all(self) -> None:
        self.restore_data({t: [] for t in TABLES})

    def export_json(self, path: str | Path) -> dict:
        payload = {
            "format": BACKUP_FORMAT,
            "schema_version": SCHEMA_VERSION,
            "app_version": APP_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "settings": {k: v for k, v in self.all_settings().items()
                         if k in ("company_name", "company_address", "currency")},
            "data": self.dump_data(),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return {t: len(v) for t, v in payload["data"].items()}

    def export_db_copy(self, path: str | Path) -> None:
        dest = sqlite3.connect(str(path))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

    @staticmethod
    def read_backup_file(path: str | Path) -> dict:
        """Lit un fichier .json (ou .db) et renvoie un payload validé.

        Lève ``BackupValidationError`` si le contenu n'est pas conforme.
        """
        path = str(path)
        if path.lower().endswith((".db", ".sqlite", ".sqlite3")):
            payload = Database._payload_from_sqlite(path)
        else:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            except json.JSONDecodeError as exc:
                raise BackupValidationError([f"Fichier JSON invalide : {exc}"]) from exc
        Database.validate_backup(payload)
        return payload

    @staticmethod
    def _payload_from_sqlite(path: str) -> dict:
        try:
            src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            src.row_factory = sqlite3.Row
            data = {}
            for table in TABLES:
                cols = ", ".join(c[0] for c in COLUMNS[table])
                data[table] = [dict(r) for r in src.execute(
                    f"SELECT {cols} FROM {table} ORDER BY id")]
            settings = {}
            try:
                settings = {r["key"]: r["value"] for r in src.execute(
                    "SELECT key, value FROM settings")}
            except sqlite3.Error:
                pass
            src.close()
        except sqlite3.Error as exc:
            raise BackupValidationError([f"Base SQLite illisible ou incompatible : {exc}"]) from exc
        return {"format": BACKUP_FORMAT, "schema_version": SCHEMA_VERSION,
                "settings": settings, "data": data}

    @staticmethod
    def validate_backup(payload: Any) -> None:
        errors: list[str] = []
        if not isinstance(payload, dict):
            raise BackupValidationError(["La racine du fichier doit être un objet JSON."])
        if payload.get("format") != BACKUP_FORMAT:
            errors.append(f"Champ « format » absent ou différent de « {BACKUP_FORMAT} ».")
        version = payload.get("schema_version")
        if not isinstance(version, int) or version > SCHEMA_VERSION:
            errors.append(f"Version de schéma non prise en charge : {version!r}.")
        data = payload.get("data")
        if not isinstance(data, dict):
            errors.append("Section « data » absente ou invalide.")
            raise BackupValidationError(errors)

        ids: dict[str, set] = {}
        for table in TABLES:
            rows = data.get(table)
            if not isinstance(rows, list):
                errors.append(f"Table « {table} » absente ou n'est pas une liste.")
                ids[table] = set()
                continue
            seen = set()
            for i, row in enumerate(rows):
                where = f"{table}[{i}]"
                if not isinstance(row, dict):
                    errors.append(f"{where} : enregistrement invalide.")
                    continue
                for col, types, required, nullable in COLUMNS[table]:
                    val = row.get(col)
                    if val is None:
                        if required and not nullable:
                            errors.append(f"{where} : champ obligatoire « {col} » manquant.")
                        continue
                    if isinstance(val, bool) or not isinstance(val, types):
                        errors.append(f"{where} : type invalide pour « {col} ».")
                if "rate_type" in row and row.get("rate_type") not in ("fixed", "percent"):
                    errors.append(f"{where} : « rate_type » doit valoir 'fixed' ou 'percent'.")
                rid = row.get("id")
                if rid in seen:
                    errors.append(f"{where} : identifiant {rid} en double.")
                seen.add(rid)
            ids[table] = seen

        for (table, col), target in FOREIGN_KEYS.items():
            for i, row in enumerate(data.get(table) or []):
                if isinstance(row, dict) and row.get(col) is not None \
                        and row[col] not in ids.get(target, set()):
                    errors.append(f"{table}[{i}] : référence « {col} »={row[col]} introuvable "
                                  f"dans « {target} ».")
        if errors:
            raise BackupValidationError(errors)

    # ------------------------------------------------------------------ #
    # Données de démonstration
    # ------------------------------------------------------------------ #
    def load_demo_data(self) -> None:
        from demo_data import build_demo_dataset
        self.restore_data(build_demo_dataset())
