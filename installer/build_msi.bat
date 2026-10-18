@echo off
rem Rebuilds BlockForge.exe and BlockForge-<version>.msi. Bump VERSION for each new release.
set VERSION=1.1.1
cd /d "%~dp0"
python -m PyInstaller BlockForge.spec --noconfirm --distpath dist --workpath build || exit /b 1
wix build BlockForge.wxs -arch x64 -ext WixToolset.Util.wixext -d Version=%VERSION% -o BlockForge-%VERSION%.msi || exit /b 1
echo Built BlockForge-%VERSION%.msi
