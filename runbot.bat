@echo off
:start
pip install --upgrade git+https://github.com/Rapptz/discord.py@async
cls
python run.py
goto start