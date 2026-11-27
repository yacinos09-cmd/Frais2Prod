"""
Jeu de données de démonstration (montants en FDJ).
Permet de tester immédiatement toutes les fonctionnalités de l'application.
"""
from __future__ import annotations

from datetime import date, timedelta


def build_demo_dataset() -> dict[str, list[dict]]:
    today = date.today()

    def d(days_ago: int) -> str:
        return (today - timedelta(days=days_ago)).isoformat()

    workers = [
        (1, "Amina Hassan", "amina.hassan@exemple.dj", "+253 77 12 34 56", "Voix chaude, FR/AR/EN"),
        (2, "Karim Ali Omar", "karim.omar@exemple.dj", "+253 77 23 45 67", "Réalisateur pub & corporate"),
        (3, "Sophie Martin", "sophie.martin@exemple.fr", "+33 6 12 34 56 78", "Productrice exécutive"),
        (4, "Yacin Robleh", "yacin.robleh@exemple.dj", "+253 77 34 56 78", "Cadreur / drone certifié"),
        (5, "Fatouma Ibrahim", "fatouma.ibrahim@exemple.dj", "+253 77 45 67 89", "Monteuse & étalonneuse"),
        (6, "Lucas Bernard", "lucas.bernard@exemple.fr", "+33 6 98 76 54 32", "Ingénieur du son / mixage"),
        (7, "Hodan Abdi", "hodan.abdi@exemple.dj", "+253 77 56 78 90", "Motion designer"),
        (8, "Moussa Djama", "moussa.djama@exemple.dj", "+253 77 67 89 01", "Régisseur général"),
    ]
    roles = [
        # (id, worker_id, role, rate_type, rate_value)
        (1, 1, "Voix off", "fixed", 60000),
        (2, 1, "Comédien", "fixed", 90000),
        (3, 2, "Réalisateur", "percent", 20),
        (4, 3, "Producteur", "percent", 10),
        (5, 3, "Directeur de production", "fixed", 150000),
        (6, 4, "Cadreur", "fixed", 70000),
        (7, 4, "Chef opérateur", "fixed", 110000),
        (8, 5, "Monteur", "percent", 35),
        (9, 5, "Étalonneur", "fixed", 80000),
        (10, 6, "Ingénieur du son", "fixed", 65000),
        (11, 6, "Mixeur", "percent", 25),
        (12, 7, "Motion designer", "fixed", 120000),
        (13, 8, "Régisseur", "fixed", 45000),
    ]
    projects = [
        (1, "Spot TV – Lancement Télécom 5G", "Djibouti Telecom", d(40), "Livré",
         "Spot 30 s + déclinaison 15 s, diffusion RTD et réseaux sociaux."),
        (2, "Film institutionnel – Port de Doraleh", "Port Autorité", d(18), "Post-production",
         "Film de 3 min, version FR et EN."),
        (3, "Campagne radio – Banque Salaam", "Salaam Bank", d(5), "En préparation",
         "3 spots radio de 30 s."),
    ]
    invoices = [
        (1, 1, "FAC-2026-014", d(35), 2500000, "Acompte 60 %"),
        (2, 1, "FAC-2026-019", d(10), 1600000, "Solde à la livraison"),
        (3, 2, "FAC-2026-021", d(15), 3200000, "Acompte 50 %"),
        (4, 3, "FAC-2026-025", d(3), 450000, "Acompte 50 %"),
    ]
    expenses = [
        # (id, project_id, invoice_id, label, category, date, amount, notes)
        (1, 1, 1, "Journée de tournage studio", "Tournage", d(38), 850000, "2 caméras, studio A"),
        (2, 1, 1, "Enregistrement voix off FR/AR", "Voix off", d(36), 180000, None),
        (3, 1, 2, "Montage, étalonnage et mixage", "Post-production", d(30), 600000, None),
        (4, 1, None, "Location drone + assurance", "Location matériel", d(38), 120000, None),
        (5, 2, 3, "Tournage 2 jours – terminal à conteneurs", "Tournage", d(16), 1400000, None),
        (6, 2, 3, "Habillage graphique et motion design", "Motion design", d(12), 360000, None),
        (7, 2, None, "Régie et autorisations de tournage", "Régie", d(17), 150000, None),
        (8, 3, 4, "Enregistrement 3 spots radio", "Voix off", d(2), 240000, None),
    ]
    allocations = [
        # (id, expense_id, worker_id, role, rate_type, rate_value, notes)
        (1, 1, 2, "Réalisateur", "percent", 20, None),
        (2, 1, 3, "Producteur", "percent", 10, None),
        (3, 1, 4, "Chef opérateur", "fixed", 110000, None),
        (4, 1, 8, "Régisseur", "fixed", 45000, None),
        (5, 1, 6, "Ingénieur du son", "fixed", 65000, None),
        (6, 2, 1, "Voix off", "fixed", 120000, "2 langues"),
        (7, 2, 6, "Ingénieur du son", "fixed", 60000, None),
        (8, 3, 5, "Monteur", "percent", 35, None),
        (9, 3, 5, "Étalonneur", "fixed", 80000, None),
        (10, 3, 6, "Mixeur", "percent", 25, None),
        (11, 4, 4, "Cadreur", "fixed", 70000, "Pilote drone"),
        (12, 5, 2, "Réalisateur", "percent", 20, None),
        (13, 5, 4, "Chef opérateur", "fixed", 220000, "2 jours"),
        (14, 5, 3, "Directeur de production", "fixed", 150000, None),
        (15, 5, 8, "Régisseur", "fixed", 90000, "2 jours"),
        (16, 6, 7, "Motion designer", "fixed", 240000, "2 versions"),
        (17, 7, 8, "Régisseur", "fixed", 45000, None),
        (18, 8, 1, "Voix off", "fixed", 180000, "3 spots"),
    ]

    return {
        "workers": [dict(id=i, name=n, email=e, phone=p, notes=no) for i, n, e, p, no in workers],
        "worker_roles": [dict(id=i, worker_id=w, role=r, rate_type=t, rate_value=float(v))
                         for i, w, r, t, v in roles],
        "projects": [dict(id=i, name=n, client=c, date=dt, status=s, notes=no)
                     for i, n, c, dt, s, no in projects],
        "invoices": [dict(id=i, project_id=p, reference=r, date=dt, amount=float(a), notes=no)
                     for i, p, r, dt, a, no in invoices],
        "expenses": [dict(id=i, project_id=p, invoice_id=inv, label=l, category=c, date=dt,
                          amount=float(a), notes=no)
                     for i, p, inv, l, c, dt, a, no in expenses],
        "allocations": [dict(id=i, expense_id=e, worker_id=w, role=r, rate_type=t,
                             rate_value=float(v), notes=no)
                        for i, e, w, r, t, v, no in allocations],
    }
