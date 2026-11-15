@echo off
rem Cardia: puesta en marcha completa (doble clic o "setup.cmd [opciones]").
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0setup.ps1" %*
if errorlevel 1 pause
