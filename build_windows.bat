@echo off
REM ==========================================================================
REM  Compilation de GestionProduction.exe (Windows 10/11, Python 3.10+)
REM  Résultat : dist\GestionProduction.exe (exécutable autonome, un seul fichier)
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo [1/3] Creation de l'environnement virtuel...
    py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [2/3] Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist assets\icon.ico python assets\make_icon.py

echo [3/3] Compilation PyInstaller...
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name GestionProduction ^
    --icon assets\icon.ico ^
    --add-data "assets;assets" ^
    --hidden-import platformdirs ^
    --exclude-module tkinter ^
    main.py

if errorlevel 1 (
    echo.
    echo ECHEC de la compilation.
    exit /b 1
)
echo.
echo Termine : dist\GestionProduction.exe
endlocal
