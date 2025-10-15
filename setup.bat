@echo off
chcp 65001 >nul
title Быстрая настройка Duty App

echo 🚀 Быстрая настройка Duty Schedule App
echo.

set "APP_DIR=%~dp0"
set "ENV_FILE=%APP_DIR%.env"

if exist "%ENV_FILE%" (
    echo Файл .env уже существует.
    set /p OVERWRITE="Перезаписать? [y/N]: "
    if /i not "%OVERWRITE%"=="y" goto EXIT
)

:GET_URL
set /p GOOGLE_SHEET_URL="Введите URL Google таблицы: "
if "%GOOGLE_SHEET_URL%"=="" (
    echo URL не может быть пустым!
    goto GET_URL
)

(
echo GOOGLE_SHEET_URL=%GOOGLE_SHEET_URL%
echo GOOGLE_CREDENTIALS_FILE=credentials.json
echo FLASK_DEBUG=False
) > "%ENV_FILE%"

echo ✅ Настройка завершена!
echo 📁 Файл .env создан

if not exist "%APP_DIR%credentials.json" (
    echo.
    echo ⚠️  Не забудьте добавить файл credentials.json в папку приложения!
)

echo.
pause

:EXIT