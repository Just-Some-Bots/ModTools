@echo off
chcp 65001
COLOR 02
pip install --upgrade git+https://github.com/Rapptz/discord.py@async
:start
cls
python run.py
goto start