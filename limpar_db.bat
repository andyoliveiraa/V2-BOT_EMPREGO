@echo off
chcp 65001 > nul
echo ===================================================
echo     Project-Emprego - Limpar Banco de Dados
echo ===================================================
echo.
echo Tem a certeza de que deseja limpar a base de dados?
echo Isto ira apagar todas as configurações e histórico de vagas!
echo.
pause
echo.
if exist "antigravity.db" (
    del /f /q "antigravity.db"
    echo.
    echo [SUCESSO] A base de dados 'antigravity.db' foi apagada!
) else (
    echo.
    echo [INFO] O ficheiro 'antigravity.db' não existe na pasta atual.
)
echo.
echo Concluído. A base de dados será recriada limpa ao iniciar o bot.
echo.
pause
