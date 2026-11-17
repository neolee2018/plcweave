@echo off
rem Real L01S test on COM11 (RS485) + COM5 (programming port). Add --restart only when intended.
setlocal
set "PLCWEAVE_ROOT=%~dp0"
pushd "%PLCWEAVE_ROOT%"
if exist "%PLCWEAVE_ROOT%.venv\Scripts\python.exe" (
    "%PLCWEAVE_ROOT%.venv\Scripts\python.exe" -m plcweave.bench --script "%PLCWEAVE_ROOT%project\l01s-water-standard\run_hil_v3.py" --script-args %*
) else (
    python -m plcweave.bench --script "%PLCWEAVE_ROOT%project\l01s-water-standard\run_hil_v3.py" --script-args %*
)
popd
endlocal
