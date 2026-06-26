@echo off
cd /d C:\Users\ufo\Documents\ouffo_work_space\logement_project

docker info >nul 2>&1
if errorlevel 1 (
    echo Docker Desktop n'est pas lancé.
    exit /b 1
)


echo Starting Docker pipeline at %date% %time%
docker compose run --rm -T pipeline

echo Docker finished with code %ERRORLEVEL%
exit /b %ERRORLEVEL%