@echo off
echo ==============================================
echo AcousticStudio C++ Acceleration Build Script
echo ==============================================

:: Check for GCC (MinGW)
where g++ >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] g++ compiler found.
    echo Building sonic_core.dll using g++...
    g++ -O3 -shared -fPIC sonic_core.cpp -o sonic_core.dll
    if %ERRORLEVEL% equ 0 (
        echo [SUCCESS] sonic_core.dll generated successfully!
        exit /b 0
    ) else (
        echo [ERROR] g++ build failed.
        exit /b 1
    )
)

:: Check for MSVC (cl.exe)
where cl >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] MSVC compiler found.
    echo Building sonic_core.dll using cl.exe...
    cl /LD /O2 /EHsc sonic_core.cpp /link /OUT:sonic_core.dll
    if %ERRORLEVEL% equ 0 (
        echo [SUCCESS] sonic_core.dll generated successfully!
        del sonic_core.obj
        del sonic_core.lib
        del sonic_core.exp
        exit /b 0
    ) else (
        echo [ERROR] MSVC build failed.
        exit /b 1
    )
)

echo [ERROR] No C++ compiler found (g++ or cl.exe).
echo Please install MinGW-w64 (GCC) or Visual Studio Build Tools (C++).
echo Make sure the compiler is added to your system PATH.
exit /b 1
