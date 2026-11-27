# -*- mode: python ; coding: utf-8 -*-
# Fichier de configuration PyInstaller multiplateforme (Windows / macOS).
#   pyinstaller --noconfirm --clean GestionProduction.spec
import sys

APP_NAME = "GestionProduction"
ICON = "assets/icon.ico" if sys.platform.startswith("win") else "assets/icon.png"

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=["platformdirs", "reportlab.graphics.barcode.common"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,          # application graphique : pas de console
    icon=ICON,
    argv_emulation=False,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier="com.studioprod.gestionproduction",
        info_plist={
            "CFBundleDisplayName": "Gestion de Production",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleDevelopmentRegion": "fr",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
