"""
Gestionnaire d'historique Annuler / Rétablir.

Stratégie : instantanés d'état. Avant chaque opération d'écriture, l'état
complet des données est sérialisé en mémoire (dictionnaire JSON-compatible).
Annuler restaure l'instantané précédent ; l'état courant est empilé côté
« Rétablir ». Cette approche couvre uniformément toutes les opérations,
y compris les imports de sauvegarde et la réinitialisation de démonstration,
et reste très légère pour la volumétrie d'une société de production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from database import Database


@dataclass
class HistoryEntry:
    description: str
    snapshot: dict


class HistoryManager:
    def __init__(self, db: Database, limit: int = 200):
        self.db = db
        self.limit = limit
        self._undo: list[HistoryEntry] = []
        self._redo: list[HistoryEntry] = []
        self._listeners: list[Callable[[], None]] = []

    # -- abonnement ---------------------------------------------------- #
    def subscribe(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    # -- exécution ------------------------------------------------------ #
    def execute(self, description: str, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Exécute une opération en l'enregistrant dans l'historique."""
        before = self.db.dump_data()
        try:
            result = func(*args, **kwargs)
        except Exception:
            # Sécurité : on revient à l'état exact d'avant l'opération.
            self.db.restore_data(before)
            raise
        self._undo.append(HistoryEntry(description, before))
        if len(self._undo) > self.limit:
            self._undo.pop(0)
        self._redo.clear()
        self._notify()
        return result

    def undo(self) -> str | None:
        if not self._undo:
            return None
        entry = self._undo.pop()
        current = self.db.dump_data()
        self.db.restore_data(entry.snapshot)
        self._redo.append(HistoryEntry(entry.description, current))
        self._notify()
        return entry.description

    def redo(self) -> str | None:
        if not self._redo:
            return None
        entry = self._redo.pop()
        current = self.db.dump_data()
        self.db.restore_data(entry.snapshot)
        self._undo.append(HistoryEntry(entry.description, current))
        self._notify()
        return entry.description

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._notify()

    # -- état ----------------------------------------------------------- #
    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo_text(self) -> str:
        return self._undo[-1].description if self._undo else ""

    def redo_text(self) -> str:
        return self._redo[-1].description if self._redo else ""

    def undo_count(self) -> int:
        return len(self._undo)

    def redo_count(self) -> int:
        return len(self._redo)
