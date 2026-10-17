@echo off
REM One-click setup and run on Windows (Anaconda / Miniconda Prompt).
cd /d %~dp0
call conda create -n algoguard python=3.11 -y
call conda activate algoguard
pip install -r requirements.txt
python -m pytest -q tests
python run.py --download
python run.py
python paper_trade.py --days 60
streamlit run app.py
