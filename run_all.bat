@echo off
REM One-click check on Windows (Anaconda / Miniconda Prompt): install, then re-run and verify every result.
cd /d %~dp0
call conda create -n algoguard python=3.11 -y
call conda activate algoguard
pip install -r requirements.txt
python verify.py
python paper_trade.py --days 60
streamlit run app.py
