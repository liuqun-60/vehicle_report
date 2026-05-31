@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo  X 试验报告系统 - SQLite 演示版
echo  工作目录: %CD%
echo ========================================

where py >nul 2>&1
if %errorlevel%==0 (
    set PY=py -3
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PY=python
    ) else (
        echo [错误] 未找到 Python，请先安装 Python 3.9+
        pause
        exit /b 1
    )
)

echo.
echo [1/2] 初始化 SQLite 数据库...
set PYTHONIOENCODING=utf-8
%PY% "%~dp0init_demo_db.py"
if errorlevel 1 (
    echo [错误] 数据库初始化失败
    pause
    exit /b 1
)

echo.
echo [2/2] 启动 Streamlit...
%PY% -m streamlit run "%~dp0app.py" --server.headless true
pause
