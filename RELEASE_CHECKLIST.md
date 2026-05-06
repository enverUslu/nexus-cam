# Release Checklist

Before publishing a release:

1. Build on Windows with `.\packaging\build-windows.ps1`.
2. Compile `packaging\installer-windows.iss` with Inno Setup.
3. Install `NexusCam-Setup-v0.1.0.exe` on a clean Windows user account.
4. Launch from the Start Menu and confirm the launcher opens.
5. Click `Open Browser` and confirm the web app opens.
6. Put the camera in `AllShare Play` / `Samsung Link`.
7. Run Discover, Browse, and one small test download.
8. Confirm the download folder opens from the folder button.
9. Confirm the app exits from the launcher Stop button.
10. Do not attach camera dumps, private media, firmware files, or local test downloads to the release.
11. On macOS, build `dist/installer/NexusCam-v0.1.0-macOS.dmg` and confirm the app launches from the mounted DMG.
