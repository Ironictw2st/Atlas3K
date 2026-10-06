@echo off
rem Opens BOB's hidden Preferences Editor. Add --ak "<kit root>" to use another assembly kit.
python "%~dp0bob_prefs.py" %*
if errorlevel 1 pause
