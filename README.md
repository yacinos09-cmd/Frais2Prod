# Gestion de Production — application desktop (Windows / macOS)

Application de bureau en **Python + PySide6** pour une société de production audiovisuelle et publicitaire :
projets, factures clients encaissées, frais de production, **répartition des montants entre intervenants**,
rapports **PDF**, **Annuler / Rétablir** complet et **sauvegarde / restauration** de la base.

---

## 1. Démarrage rapide (développement)

```bash
# Python 3.10 ou plus récent
python -m venv .venv
# Windows : .venv\Scripts\activate      macOS : source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Au premier lancement, la base est créée et remplie avec un **jeu de données de démonstration**
(3 projets, 8 intervenants, 8 frais, 18 répartitions). Bouton **« ⟳ Données de démo »** pour réinitialiser
à tout moment (action annulable).

## 2. Compilation en exécutable autonome

### Compilation automatique sur GitHub (recommandé)
Le fichier `.github/workflows/build.yml` compile l'application sur les serveurs de GitHub,
sous Windows et sous macOS, sans rien installer sur votre ordinateur :

- **À chaque envoi sur `main`** : onglet **Actions** → dernière exécution « Compilation des exécutables »
  → section **Artifacts** : `GestionProduction-Windows` (contient le `.exe`) et `GestionProduction-macOS`
  (contient le `.app`). Conservés 30 jours.
- **À la demande** : onglet **Actions** → « Compilation des exécutables » → bouton **Run workflow**.
- **Version officielle** : créez un tag commençant par `v` (ex. `v1.0.0`, via **Releases → Draft a new release**
  ou `git tag v1.0.0 && git push --tags`). Les deux exécutables sont alors joints automatiquement
  à la page **Releases**, en téléchargement direct.

L'app macOS est compilée pour les Mac Apple Silicon (M1 et suivants). Les exécutables ne sont pas signés :
première ouverture sous Windows → « Informations complémentaires » → « Exécuter quand même » ;
sous macOS → clic droit sur l'app → « Ouvrir ».

### Compilation manuelle

> Les icônes `assets/icon.png` / `icon.ico` sont générées automatiquement par les scripts de build. En cas de compilation manuelle, lancez d'abord `python assets/make_icon.py`.

> PyInstaller ne fait pas de compilation croisée : on compile le `.exe` **sur Windows** et le `.app` **sur macOS**.

### Windows → `dist\GestionProduction.exe`
Double-cliquer sur `build_windows.bat`, ou à la main :
```bat
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name GestionProduction ^
    --icon assets\icon.ico ^
    --add-data "assets;assets" ^
    --hidden-import platformdirs ^
    --exclude-module tkinter ^
    main.py
```

### macOS → `dist/GestionProduction.app`
```bash
chmod +x build_macos.sh && ./build_macos.sh
```
ou à la main :
```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed \
  --name GestionProduction \
  --icon assets/icon.png \
  --osx-bundle-identifier com.studioprod.gestionproduction \
  --add-data "assets:assets" \
  --hidden-import platformdirs \
  --exclude-module tkinter \
  main.py
```
(Pillow, inclus dans `requirements.txt`, convertit automatiquement l'icône PNG en `.icns`.)

### Alternative : fichier `.spec` commun
```bash
pyinstaller --noconfirm --clean GestionProduction.spec
```
Produit un dossier `dist/GestionProduction/` (démarrage plus rapide qu'un `--onefile`) et, sur macOS, le bundle `.app`.

### Gestion des chemins une fois packagé
- **Ressources embarquées** (icône…) : `utils.resource_path()` utilise `sys._MEIPASS` quand l'application est packagée,
  sinon le dossier du code source.
- **Base de données** : jamais à côté de l'exécutable (souvent en lecture seule dans `Program Files` ou dans un `.app` signé),
  mais dans le dossier utilisateur standard fourni par `platformdirs` :

| Système | Emplacement de `production_data.db` |
|---|---|
| Windows | `%LOCALAPPDATA%\StudioProd\GestionProduction\` |
| macOS | `~/Library/Application Support/GestionProduction/` |
| Linux | `~/.local/share/GestionProduction/` |

Menu **Fichier → Ouvrir le dossier des données** pour y accéder. Un journal `application.log` y est aussi écrit.
La variable d'environnement `GESTION_PROD_DB` permet d'utiliser une autre base (tests).

> **Distribution macOS** : sans signature Apple, Gatekeeper peut bloquer la première ouverture
> (clic droit → Ouvrir). Pour diffuser largement : `codesign` + notarisation avec un compte Apple Developer.
> **Windows** : SmartScreen peut afficher un avertissement tant que l'exécutable n'est pas signé.

## 3. Fonctionnalités

### Interface (entièrement en français)
Barre d'outils permanente : **Annuler**, **Rétablir**, **Exporter BDD**, **Importer BDD**, Données de démo, Paramètres,
et **sélecteur de devise** (FDJ, EUR, USD, XOF, XAF, MAD, CAD, CHF, GBP — devise d'affichage, sans conversion).

| Onglet | Contenu |
|---|---|
| **Tableau de bord** | Total encaissé, total des frais, total réparti, reste à répartir, marge ; gains par intervenant ; synthèse par projet (double-clic → ouvre le projet) |
| **Projets & Répartitions** | Liste filtrable des projets ; factures payées ; frais de production ; grille de répartition avec **montant / réparti / reste** en temps réel (pastille rouge + barre rouge en cas de dépassement) ; bouton **« Exporter PDF du frais »** |
| **Travailleurs & Barèmes** | Référentiel indépendant : nom, contact, **plusieurs métiers** chacun avec un barème par défaut (montant fixe ou %) ; détail des participations et gains cumulés |
| **Rapport Global PDF** | Aperçu arborescent des gains par personne, filtre par projet, bouton **« Générer le PDF Global »** |

### Logique de répartition
- Un frais peut être rattaché à une facture client du projet.
- En affectant un intervenant, ses métiers sont proposés et **le barème du métier se pré-remplit** ;
  il reste modifiable pour ce frais précis (fixe ↔ pourcentage).
- Un pourcentage s'applique au montant du frais. Si le montant du frais change, les parts en % sont recalculées.
- La boîte de répartition affiche en direct : montant du frais, déjà réparti, cette part, **reste** ;
  bouton **« Attribuer le reste »**. Un dépassement est signalé en rouge et demande confirmation.

### Annuler / Rétablir
- Raccourcis : **Ctrl+Z / Cmd+Z** (annuler), **Ctrl+Y / Cmd+Shift+Z / Ctrl+Shift+Z** (rétablir).
- Couvre **toutes** les opérations : ajout / modification / suppression de projets, factures, frais, répartitions,
  intervenants — ainsi que l'**import**, la réinitialisation démo et le vidage de la base.
- Implémentation (`history.py`) : instantané complet des données avant chaque opération, restauré de façon
  transactionnelle. Boutons activés/désactivés dynamiquement, info-bulle « Annuler : … », message dans la barre de statut.
  Historique limité aux 200 dernières opérations, en mémoire (réinitialisé à la fermeture).

### Sauvegarde / restauration
- **Exporter BDD** : `backup-production-AAAA-MM-JJ.json` (lisible, portable) **ou** copie `.db` SQLite complète.
- **Importer BDD** : `.json` ou `.db`. Validation du schéma **avant** toute modification (champs obligatoires, types,
  doublons d'identifiants, cohérence des références) ; en cas d'erreur, le détail est affiché et rien n'est modifié.
  Puis demande de confirmation, remplacement, rafraîchissement de toutes les vues — **annulable** par Ctrl+Z.

Format JSON :
```json
{
  "format": "gestion-production-backup",
  "schema_version": 1,
  "exported_at": "2026-11-27T14:00:00",
  "settings": {"company_name": "...", "company_address": "...", "currency": "FDJ"},
  "data": {"workers": [], "worker_roles": [], "projects": [], "invoices": [], "expenses": [], "allocations": []}
}
```

### Rapports PDF (ReportLab, aucune dépendance externe)
1. **PDF par frais** : en-tête société, projet, client, intitulé ; encadré montant / réparti / solde ; facture associée ;
   tableau intervenant · métier · barème · part · montant ; sous-total et solde restant (alerte si dépassement).
2. **PDF global par personne** : périmètre (tous les projets ou un projet) ; pour chaque intervenant ses métiers,
   le détail projets/frais/montants et son **gain total cumulé** ; **tableau récapitulatif final** avec total général.
   Pagination « Page X / Y » et date de génération en pied de page.

Le nom et les coordonnées de la société (en-tête des PDF) se règlent dans **⚙ Paramètres**, ainsi que l'ouverture
automatique des PDF après génération.

## 4. Organisation du code

```
main.py              Point d'entrée : QApplication, thème, journalisation, gestion d'erreurs, ouverture de la base
database.py          SQLite : schéma, CRUD, agrégats/rapports, instantanés, export/import JSON & .db, validation
history.py           Gestionnaire Annuler / Rétablir (instantanés d'état)
pdf_generator.py     Les deux rapports PDF (ReportLab)
ui_main.py           Fenêtre principale, barre d'outils, menus, 4 onglets
ui_dialogs.py        Boîtes de saisie (projet, facture, frais, intervenant, répartition, paramètres)
styles.py            Feuille de style QSS et palette
utils.py             Chemins (sys._MEIPASS, platformdirs), formats monétaires FR, référentiels métier
demo_data.py         Jeu de données de démonstration
assets/              Icône (générée par assets/make_icon.py ; automatique lors du build)
requirements.txt     Dépendances
build_windows.bat    Compilation .exe
build_macos.sh       Compilation .app
GestionProduction.spec  Configuration PyInstaller commune
```

### Schéma de données
`workers` (intervenants) → `worker_roles` (métiers + barème par défaut)
`projects` → `invoices` (factures encaissées) et `expenses` (frais, lien optionnel vers une facture)
`expenses` → `allocations` (intervenant, métier, barème appliqué : `fixed` | `percent`)

Les montants dus sont calculés à la volée (`utils.allocation_amount`), ce qui garantit la cohérence
quand un montant de frais est modifié. Clés étrangères avec suppression en cascade.
