@echo off
setlocal enabledelayedexpansion

REM Intentar primero sin entorno virtual
echo Intentando ejecutar sin entorno virtual...
pythonw -c "import pysftp" >nul 2>&1
if %errorlevel% equ 0 (
    echo Dependencias encontradas en Python global, ejecutando aplicación...
    start /b pythonw connectionFTP.py
    exit /b 0
)

REM Si falla, buscar el entorno virtual en .env
echo Buscando entorno virtual...
for /f "tokens=1,* delims==" %%a in ('type .env ^| findstr /i "VENV_PATH"') do (
    set "venv_path=%%b"
    REM Eliminar espacios en blanco
    set "venv_path=!venv_path: =!"
)

if not defined venv_path (
    echo Error: No se encontró VENV_PATH en el archivo .env
    echo Agregue VENV_PATH=ruta/a/tu/entorno/virtual en el archivo .env
    pause
    exit /b 1
)

REM Verificar si existe el entorno virtual
if not exist "!venv_path!\Scripts\activate.bat" (
    echo Error: No se encontró el entorno virtual en !venv_path!
    echo Verifique que la ruta en VENV_PATH sea correcta
    pause
    exit /b 1
)

REM Activar entorno virtual y ejecutar la aplicación
echo Activando entorno virtual en !venv_path!
call "!venv_path!\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Error: No se pudo activar el entorno virtual
    pause
    exit /b 1
)

echo Ejecutando aplicación...
start /b pythonw connectionFTP.py
if %errorlevel% neq 0 (
    echo Error: No se pudo ejecutar la aplicación
    pause
    exit /b 1
)

endlocal