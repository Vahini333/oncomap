@echo off
REM Run this from "Git Bash" or "Command Prompt" after Git is installed.
REM Or: right-click folder -> "Git Bash Here", then run: bash push_to_github.bat
cd /d "%~dp0"
echo Checking for Git...
git --version 2>nul || (
  echo Git not found. Install from https://git-scm.com/download/win
  echo Then open "Git Bash" from Start menu and run: cd /c/Users/madhu/Downloads/vibeathon
  echo Then run: git init ^&^& git remote add origin https://github.com/Vahini333/oncomap.git ^&^& git add . ^&^& git commit -m "Add vibeathon code" ^&^& git branch -M main ^&^& git push -u origin main
  pause
  exit /b 1
)
if not exist .git git init
git remote remove origin 2>nul
git remote add origin https://github.com/Vahini333/oncomap.git
git add .
git status
git commit -m "Add vibeathon: VCF upload, PDAC report, template PDF workflow"
git branch -M main
echo.
echo Pushing to https://github.com/Vahini333/oncomap ...
git push -u origin main
echo.
pause
