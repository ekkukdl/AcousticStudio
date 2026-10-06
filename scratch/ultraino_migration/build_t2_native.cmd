@echo off
setlocal
if not defined STUDIO_VCVARS (
    echo Set STUDIO_VCVARS to an existing Visual Studio vcvars64.bat.
    exit /b 1
)
call "%STUDIO_VCVARS%" >nul
if errorlevel 1 exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /LD /EHsc /openmp ../../src/acousticstudio/sonic_core.cpp /Fe:sonic_core_t2.dll /Fo:sonic_core_t2.obj /link /IMPLIB:sonic_core_t2.lib
exit /b %ERRORLEVEL%
