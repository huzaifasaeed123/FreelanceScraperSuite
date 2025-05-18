@echo off
echo Starting Facebook Bot build process...

echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "FacebookBot.spec" del "FacebookBot.spec"

echo Building executable...
pyinstaller --clean --noconfirm --onefile ^
--add-data "config.txt;." ^
--add-data "sent_posts.json;." ^
--name "FacebookBot" main.py

echo Creating delivery folder...
mkdir "FacebookBot_Package"
copy "dist\FacebookBot.exe" "FacebookBot_Package"
copy "config.txt" "FacebookBot_Package"

echo Creating startup script...
echo @echo off > "FacebookBot_Package\Start_Bot.bat"
echo echo Starting Facebook Bot... >> "FacebookBot_Package\Start_Bot.bat"
echo start FacebookBot.exe >> "FacebookBot_Package\Start_Bot.bat"

echo Build complete! Your package is in the FacebookBot_Package folder.
pause