@echo off
setlocal
set SRC=%~dp0PowerShellCompiler.cpp
set OUT=%~dp0PowerShellCompiler.exe

where cl >nul 2>nul
if %errorlevel%==0 (
    cl /nologo /O2 /W4 /GS- /MT /DUNICODE /D_UNICODE /Fe"%OUT%" "%SRC%" shell32.lib shlwapi.lib advapi32.lib ole32.lib /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup
    goto :done
)

where g++ >nul 2>nul
if %errorlevel%==0 (
    g++ -O2 -s -static -mwindows "%SRC%" -o "%OUT%" -lshell32 -lshlwapi -ladvapi32 -lole32
    goto :done
)

echo Error: No compiler found. Install MSVC or MinGW.
exit /b 1

:done
echo Built: %OUT%
