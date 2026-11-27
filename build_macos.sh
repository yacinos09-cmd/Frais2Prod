#!/usr/bin/env bash
# ==========================================================================
#  Compilation de GestionProduction.app (macOS 11+, Python 3.10+)
#  Résultat : dist/GestionProduction.app
#  Remarque : compiler sur un Mac Apple Silicon produit une app arm64,
#             sur un Mac Intel une app x86_64.
# ==========================================================================
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[1/3] Création de l'environnement virtuel…"
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "[2/3] Installation des dépendances…"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

[ -f assets/icon.png ] || python assets/make_icon.py

echo "[3/3] Compilation PyInstaller…"
pyinstaller --noconfirm --clean --windowed \
  --name GestionProduction \
  --icon assets/icon.png \
  --osx-bundle-identifier com.studioprod.gestionproduction \
  --add-data "assets:assets" \
  --hidden-import platformdirs \
  --exclude-module tkinter \
  main.py

# Supprime l'attribut de quarantaine pour un lancement local sans alerte Gatekeeper
xattr -cr dist/GestionProduction.app || true

echo
echo "Terminé : dist/GestionProduction.app"
echo "Pour créer une archive distribuable :"
echo "  ditto -c -k --keepParent dist/GestionProduction.app dist/GestionProduction-macOS.zip"
