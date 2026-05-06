# Packaging Notes

The packaged app starts the local Nexus.cam server and shows a small control
window. The user clicks `Open Browser` to open the web app. That avoids bundling
a full browser runtime while still giving a normal app-style launch.

Recommended targets:

- macOS: PyInstaller app bundle, then a DMG.
- Windows: PyInstaller executable, then an Inno Setup installer.

## Build Commands

PyInstaller builds native executables for the platform it is running on. Build
the Windows `.exe` on Windows.

On Windows, install Python 3.11+ from python.org and enable `Add python.exe to
PATH`. Then run PowerShell from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\build-windows.ps1
```

The executable will be created at:

```text
dist\NexusCam\NexusCam.exe
```

Double-clicking the executable opens the launcher window. Click `Open Browser`
to open the web app.

## Windows Installer

Install Inno Setup, then open and compile:

```text
packaging\installer-windows.iss
```

The installer output will be:

```text
dist\installer\NexusCam-Setup-v0.1.0.exe
```

On GitHub, run the `Windows build` workflow from the Actions tab to build both
the app folder and setup installer on a Windows runner.

For a first release, prefer the one-folder PyInstaller build over `--onefile`.
It starts faster and is easier to debug if a user reports an issue.

Keep packaged releases on the same read-only transfer boundary as the source
app: discovery, UPnP ContentDirectory browsing, and HTTP GET downloads only.

## macOS Installer

Build the macOS app on macOS:

```sh
chmod +x packaging/build-macos.sh
./packaging/build-macos.sh
```

The script creates a local `.venv-build` folder for PyInstaller and does not
install packages into the system Python.

The app bundle and DMG will be created at:

```text
dist/Nexus.cam.app
dist/installer/NexusCam-v0.1.0-macOS.dmg
```

Unsigned macOS builds may require the user to allow the app in System Settings.
