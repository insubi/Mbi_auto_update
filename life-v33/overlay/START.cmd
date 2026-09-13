@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ROOT=%CD%"
set "EXE=%ROOT%\release\FishingAutomation.exe"
set "DLL=%ROOT%\FishingAutomation\interception.dll"

if not exist "%DLL%" (
  echo.
  echo Interception is not installed in this package yet.
  echo Run 1_INSTALL_INTERCEPTION.cmd first, reboot Windows, then run START.cmd again.
  echo.
  pause
  exit /b 5
)

if not exist "%EXE%" (
  call "%ROOT%\BUILD.cmd"
  if errorlevel 1 exit /b 1
)

if not exist "%ROOT%\release\templates" mkdir "%ROOT%\release\templates" >nul 2>nul
copy /y "%ROOT%\FishingAutomation\templates\hook.png" "%ROOT%\release\templates\hook.png" >nul
copy /y "%ROOT%\FishingAutomation\templates\gauge.png" "%ROOT%\release\templates\gauge.png" >nul
if exist "%ROOT%\FishingAutomation\templates\healthbar.png" copy /y "%ROOT%\FishingAutomation\templates\healthbar.png" "%ROOT%\release\templates\healthbar.png" >nul
if exist "%ROOT%\FishingAutomation\templates\compass.png" copy /y "%ROOT%\FishingAutomation\templates\compass.png" "%ROOT%\release\templates\compass.png" >nul
if exist "%ROOT%\FishingAutomation\config.json" copy /y "%ROOT%\FishingAutomation\config.json" "%ROOT%\release\config.json" >nul
if exist "%ROOT%\FishingAutomation\notification.json" if not exist "%ROOT%\release\notification.json" copy /y "%ROOT%\FishingAutomation\notification.json" "%ROOT%\release\notification.json" >nul
copy /y "%DLL%" "%ROOT%\release\interception.dll" >nul

if exist "%ROOT%\FishingAutomation\dungeon" (
  if not exist "%ROOT%\release\dungeon" mkdir "%ROOT%\release\dungeon" >nul 2>nul
  xcopy /e /i /y "%ROOT%\FishingAutomation\dungeon\*" "%ROOT%\release\dungeon\" >nul
)

if exist "%ROOT%\FishingAutomation\abyss" (
  if not exist "%ROOT%\release\abyss" mkdir "%ROOT%\release\abyss" >nul 2>nul
  xcopy /e /i /y "%ROOT%\FishingAutomation\abyss\*" "%ROOT%\release\abyss\" >nul
)

if exist "%ROOT%\FishingAutomation\life" (
  if not exist "%ROOT%\release\life" mkdir "%ROOT%\release\life" >nul 2>nul
  if not exist "%ROOT%\release\life\profile.json" copy /y "%ROOT%\FishingAutomation\life\profile.json" "%ROOT%\release\life\profile.json" >nul
  if exist "%ROOT%\FishingAutomation\life\templates" xcopy /e /i /d /y "%ROOT%\FishingAutomation\life\templates\*" "%ROOT%\release\life\templates\" >nul
)

if not exist "%EXE%" (
  echo.
  echo ERROR: FishingAutomation.exe was not created.
  echo Send build.log to ChatGPT.
  echo.
  pause
  exit /b 6
)

start "" "%EXE%"
exit /b 0
