@echo off

cd /d C:\Users\ufo\Documents\ouffo_work_space\logement_project

echo ===== CURRENT DIR =====
cd

echo ===== PYTHON =====
where python

echo ===== ACTIVATE =====
wsl bash -lc "cd /mnt/c/Users/ufo/Documents/ouffo_work_space/logement_project && source .venv/bin/activate && PYTHONPATH=. python pipelines/daily_pipelines.py"
@echo off

echo ===== PYTHON AFTER ACTIVATE =====
where python
