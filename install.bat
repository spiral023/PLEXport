@echo off
chcp 65001 >nul
title Installationsprogramm für PLEXport

SET "BASE_DIR=C:\PLEXport"
SET "LOGFILE=%BASE_DIR%\install.log"
SET "PLEXPORT_URL=https://raw.githubusercontent.com/spiral023/PLEXport/main/PLEXport.py"

if not exist "%BASE_DIR%" (
    mkdir "%BASE_DIR%"
)

echo =====================================================
echo Willkommen beim Installationsprogramm für PLEXport!
echo Dieses Skript führt folgende Schritte aus:
echo 1. Überprüfen, ob Python installiert ist
echo 2. PLEXport-Skript von GitHub herunterladen
echo 3. Alle erforderlichen Python-Pakete installieren
echo 4. PLEXport starten
echo =====================================================
echo.

echo Drücken Sie Enter, um mit Schritt 1 zu beginnen: Überprüfen ob Python installiert ist.
pause >nul

REM Schritt 1: Überprüfen, ob Python installiert ist
echo [%DATE% %TIME%] Überprüfen, ob Python installiert ist >> "%LOGFILE%"
echo Überprüfe Python-Installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python ist nicht installiert. Bitte installieren Sie Python von https://www.python.org/downloads/ >> "%LOGFILE%"
    echo [FEHLER] Python ist nicht installiert.
    echo Bitte installieren Sie Python von: https://www.python.org/downloads/
    echo Details finden Sie in "%LOGFILE%".
    echo.
    echo Drücken Sie Enter, um das Skript zu beenden.
    pause >nul
    exit /b 1
)
echo [OK] Python wurde gefunden.
echo [OK] Python wurde gefunden. >> "%LOGFILE%"
echo.

echo Schritt 1 abgeschlossen.
echo Als nächstes: Schritt 2 - Lade PLEXport.py von GitHub herunter.
echo Drücken Sie Enter, um mit Schritt 2 fortzufahren.
pause >nul

REM Schritt 2: PLEXport.py herunterladen
echo [%DATE% %TIME%] Lade PLEXport.py herunter >> "%LOGFILE%"
echo Lade PLEXport.py herunter...
powershell -Command "Invoke-WebRequest -Uri '%PLEXPORT_URL%' -OutFile '%BASE_DIR%\PLEXport.py'" >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Fehler beim Herunterladen von PLEXport.py. >> "%LOGFILE%"
    echo [FEHLER] Fehler beim Herunterladen von PLEXport.py. Bitte überprüfen Sie Internetverbindung oder URL.
    echo Details finden Sie in "%LOGFILE%".
    echo.
    echo Drücken Sie Enter, um das Skript zu beenden.
    pause >nul
    exit /b 1
)
echo [OK] PLEXport.py wurde erfolgreich heruntergeladen.
echo [OK] PLEXport.py wurde erfolgreich heruntergeladen. >> "%LOGFILE%"
echo.

echo Schritt 2 abgeschlossen.
echo Als nächstes: Schritt 3 - Installiere Python-Abhängigkeiten (pandas, plexapi, openpyxl).
echo Drücken Sie Enter, um mit Schritt 3 fortzufahren.
pause >nul

REM Schritt 3: Python-Abhängigkeiten installieren
echo [%DATE% %TIME%] Installiere Python-Abhängigkeiten >> "%LOGFILE%"
echo Installiere Python-Abhängigkeiten...
pip install pandas plexapi openpyxl >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [FEHLER] Fehler beim Installieren der Python-Abhängigkeiten. >> "%LOGFILE%"
    echo [FEHLER] Fehler beim Installieren der Python-Abhängigkeiten. Details stehen in "%LOGFILE%".
    echo.
    echo Drücken Sie Enter, um das Skript zu beenden.
    pause >nul
    exit /b 1
)
echo [OK] Python-Abhängigkeiten wurden erfolgreich installiert.
echo [OK] Python-Abhängigkeiten wurden erfolgreich installiert. >> "%LOGFILE%"
echo.

echo Schritt 3 abgeschlossen.
echo Als nächstes: Schritt 4 - Starte PLEXport.
echo Drücken Sie Enter, um mit Schritt 4 fortzufahren.
pause >nul

REM Schritt 4: PLEXport starten
echo [%DATE% %TIME%] Starte PLEXport >> "%LOGFILE%"
echo Starte PLEXport...
start "" /min python "%BASE_DIR%\PLEXport.py"
if errorlevel 1 (
    echo [FEHLER] Fehler beim Starten von PLEXport. >> "%LOGFILE%"
    echo [FEHLER] Fehler beim Starten von PLEXport. Details in "%LOGFILE%".
    echo.
    echo Drücken Sie Enter, um das Skript zu beenden.
    pause >nul
    exit /b 1
)
echo [OK] PLEXport wurde erfolgreich gestartet.
echo [OK] PLEXport wurde erfolgreich gestartet. >> "%LOGFILE%"

REM Zusammenfassung
echo =====================================================
echo Zusammenfassung:
echo - Python wurde erfolgreich überprüft.
echo - Das PLEXport-Skript wurde erfolgreich heruntergeladen.
echo - Alle Abhängigkeiten wurden erfolgreich installiert.
echo - PLEXport wurde erfolgreich gestartet.
echo =====================================================
echo.
echo Drücken Sie Enter, um das Skript zu beenden.
pause >nul
exit /b 0
