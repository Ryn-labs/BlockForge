@echo off
rem Rebuilds BlockForge.exe and BlockForge-<version>.msi.
rem The version comes from blockforge\version.py - bump it there for each new release.
cd /d "%~dp0"
pushd ..
for /f "delims=" %%v in ('python -c "import blockforge.version as v; print(v.VERSION)"') do set VERSION=%%v
popd
if "%VERSION%"=="" (echo Could not read the version from blockforge\version.py & exit /b 1)
echo Building BlockForge %VERSION%
python get_voice.py || exit /b 1
python -m PyInstaller BlockForge.spec --noconfirm --distpath dist --workpath build || exit /b 1
wix build BlockForge.wxs -arch x64 -ext WixToolset.Util.wixext -d Version=%VERSION% -o BlockForge-%VERSION%.msi || exit /b 1
echo Built BlockForge-%VERSION%.msi
