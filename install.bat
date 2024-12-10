@echo off
setlocal enabledelayedexpansion

SET BASE_DIR=C:\PLEXport
SET LOGFILE=%BASE_DIR%\install.log
SET PLEXPORT_URL=https://raw.githubusercontent.com/spiral023/PLEXport/main/PLEXport.py

if not exist %BASE_DIR% (
    mkdir %BASE_DIR%
)

echo [!date! !time!] Start Installation >> %LOGFILE%

echo [!date! !time!] Check Python installation >> %LOGFILE%
python --version >nul 2>&1
if errorlevel 1 (
    echo Python ist nicht installiert. Bitte installieren Sie Python von https://www.python.org/downloads/ >> %LOGFILE%
    echo Python ist nicht installiert. Bitte installieren Sie Python von https://www.python.org/downloads/
    exit /b 1
)
echo [!date! !time!] Python gefunden >> %LOGFILE%

echo [!date! !time!] Lade PLEXport.py herunter >> %LOGFILE%
powershell -Command "Invoke-WebRequest -Uri '%PLEXPORT_URL%' -OutFile '%BASE_DIR%\PLEXport.py'"
if errorlevel 1 (
    echo [!date! !time!] Fehler beim Herunterladen von PLEXport.py >> %LOGFILE%
    echo Fehler beim Herunterladen von PLEXport.py
    exit /b 1
)
echo [!date! !time!] PLEXport.py heruntergeladen >> %LOGFILE%

echo [!date! !time!] Install requirements >> %LOGFILE%
pip install pandas plexapi openpyxl >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo [!date! !time!] Fehler beim Installieren der Requirements >> %LOGFILE%
    echo Fehler beim Installieren der Requirements
    exit /b 1
)
echo [!date! !time!] Requirements installiert >> %LOGFILE%

echo [!date! !time!] Starte Script >> %LOGFILE%
start "" /min python %BASE_DIR%\PLEXport.py
echo [!date! !time!] Script gestartet >> %LOGFILE%

exit /b 0
