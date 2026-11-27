"""
Utilitaires transverses : chemins (compatibles PyInstaller), formatage monétaire,
dates et constantes métier.
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

APP_NAME = "GestionProduction"
APP_DISPLAY_NAME = "Gestion de Production"
APP_AUTHOR = "StudioProd"
APP_VERSION = "1.0.0"
DB_FILENAME = "production_data.db"

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #

def resource_path(relative: str) -> str:
    """Chemin absolu vers une ressource embarquée.

    Fonctionne en développement et une fois packagé par PyInstaller
    (les fichiers sont alors extraits dans ``sys._MEIPASS``).
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def user_data_dir() -> Path:
    """Dossier de données utilisateur standard (accessible en écriture).

    - Windows : %LOCALAPPDATA%\\StudioProd\\GestionProduction
    - macOS   : ~/Library/Application Support/GestionProduction
    - Linux   : ~/.local/share/GestionProduction
    """
    try:
        from platformdirs import user_data_dir as _udd
        path = Path(_udd(APP_NAME, APP_AUTHOR))
    except Exception:  # repli si platformdirs absent
        path = Path(os.path.expanduser("~")) / f".{APP_NAME.lower()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    override = os.environ.get("GESTION_PROD_DB")
    if override:
        return Path(override)
    return user_data_dir() / DB_FILENAME


def documents_dir() -> str:
    docs = Path(os.path.expanduser("~")) / "Documents"
    return str(docs if docs.is_dir() else Path(os.path.expanduser("~")))


# --------------------------------------------------------------------------- #
# Devises et montants
# --------------------------------------------------------------------------- #

CURRENCIES = {
    # code: (libellé, nombre de décimales)
    "FDJ": ("Franc djiboutien", 0),
    "EUR": ("Euro", 2),
    "USD": ("Dollar américain", 2),
    "XOF": ("Franc CFA (BCEAO)", 0),
    "XAF": ("Franc CFA (BEAC)", 0),
    "MAD": ("Dirham marocain", 2),
    "CAD": ("Dollar canadien", 2),
    "CHF": ("Franc suisse", 2),
    "GBP": ("Livre sterling", 2),
}

NBSP = " "  # espace insécable (présent dans les polices PDF standard)


def currency_decimals(currency: str) -> int:
    return CURRENCIES.get(currency, ("", 2))[1]


def format_number(value: float, decimals: int = 2) -> str:
    """Formate un nombre à la française : 1 234 567,89"""
    value = float(value or 0.0)
    negative = value < 0
    txt = f"{abs(value):,.{decimals}f}"
    txt = txt.replace(",", "\x00").replace(".", ",").replace("\x00", NBSP)
    return ("-" if negative else "") + txt


def format_money(value: float, currency: str = "EUR") -> str:
    return f"{format_number(value, currency_decimals(currency))}{NBSP}{currency}"


def format_percent(value: float) -> str:
    txt = format_number(value, 2)
    if txt.endswith(",00"):
        txt = txt[:-3]
    return f"{txt}{NBSP}%"


def format_rate(rate_type: str, rate_value: float, currency: str) -> str:
    """Barème lisible : « 15 % » ou « Forfait 50 000 FDJ »."""
    if rate_type == "percent":
        return format_percent(rate_value)
    return f"Forfait {format_money(rate_value, currency)}"


def allocation_amount(rate_type: str, rate_value: float, base_amount: float) -> float:
    """Montant revenant à un intervenant selon son barème."""
    if rate_type == "percent":
        return round(float(base_amount or 0) * float(rate_value or 0) / 100.0, 2)
    return round(float(rate_value or 0), 2)


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #

def today_iso() -> str:
    return date.today().isoformat()


def format_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:max_len] or "document"


# --------------------------------------------------------------------------- #
# Référentiels métier
# --------------------------------------------------------------------------- #

PROJECT_STATUSES = [
    "Devis",
    "En préparation",
    "En tournage",
    "Post-production",
    "Livré",
    "Clôturé",
    "Annulé",
]

EXPENSE_CATEGORIES = [
    "Tournage",
    "Voix off",
    "Réalisation",
    "Production",
    "Post-production",
    "Montage",
    "Son / Mixage",
    "Étalonnage",
    "Motion design",
    "Location matériel",
    "Régie",
    "Casting / Talents",
    "Déplacements",
    "Autre",
]

DEFAULT_ROLES = [
    "Voix off",
    "Réalisateur",
    "Producteur",
    "Directeur de production",
    "Chef opérateur",
    "Cadreur",
    "Monteur",
    "Ingénieur du son",
    "Mixeur",
    "Étalonneur",
    "Motion designer",
    "Régisseur",
    "Assistant réalisateur",
    "Maquilleur",
    "Comédien",
]

RATE_TYPES = {"fixed": "Montant fixe", "percent": "Pourcentage (%)"}
