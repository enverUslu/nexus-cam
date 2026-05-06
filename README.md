# Nexus.cam

Nexus.cam is a local web app for transferring photos and videos from Samsung Wi-Fi cameras after the old Samsung mobile apps [stopped working](https://www.wisenetlife.com/en-us/news/?seq=212).

It runs on your computer, opens in a browser, discovers the camera on the local network, shows thumbnails, and downloads selected media files. The app is read-only: it does not upload, delete, rename, change camera settings, or modify firmware.

## Download

Installers are published from the [GitHub Releases page](https://github.com/enverUslu/nexus-cam/releases/latest).

- Windows: download [`NexusCam-Setup-v0.1.0.exe`](https://github.com/enverUslu/nexus-cam/releases/latest/download/NexusCam-Setup-v0.1.0.exe)
- macOS: download [`NexusCam-v0.1.0-macOS.dmg`](https://github.com/enverUslu/nexus-cam/releases/latest/download/NexusCam-v0.1.0-macOS.dmg)

Unsigned macOS builds may require right-clicking the app and choosing `Open`, or allowing it in System Settings after the first launch attempt.

## Privacy

Nexus.cam runs locally on your computer at `127.0.0.1`. It does not use a cloud service or send media anywhere except to the download folder you choose.

You can set the download folder to iCloud Drive, OneDrive, Google Drive, or another synced folder if you want your downloaded media to sync through your preferred cloud provider.

## Compatibility

Nexus.cam is tested with the Samsung WB200F. It should also work with Samsung SMART Camera models that expose the same DLNA / UPnP media-sharing service, but those models still need confirmation from users.

If you test another model, reports are welcome through GitHub issues or by email at `njordblaviken@outlook.com`.

On the WB200F, use `AllShare Play` / `Samsung Link` media sharing mode. Remote Viewfinder mode exposes a different service and is not useful for file transfer.

The app talks to the camera through:

- SSDP discovery
- UPnP ContentDirectory `Browse`
- HTTP `GET` downloads

## Use

1. Put the camera in `AllShare Play` / `Samsung Link`.
2. Open Nexus.cam.
3. Click `Open Browser`.
4. Click `Discover`.
5. Click `Browse`.
6. Select files and download.

## Run From Source

Nexus.cam uses only the Python standard library.

```sh
python3 samsung_wifi_web.py
```

Open:

```text
http://127.0.0.1:8765
```

## Developer Builds

Build the Windows app on Windows:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\build-windows.ps1
```

Build the Windows setup installer with Inno Setup:

```text
packaging\installer-windows.iss
```

Build the macOS app and DMG on macOS:

```sh
chmod +x packaging/build-macos.sh
./packaging/build-macos.sh
```

Build outputs:

```text
dist\NexusCam\NexusCam.exe
dist\installer\NexusCam-Setup-v0.1.0.exe
dist/Nexus.cam.app
dist/installer/NexusCam-v0.1.0-macOS.dmg
```

## Command Line

The CLI is useful for diagnostics and scripted transfers:

```sh
python3 samsung_wifi_client.py discover
python3 samsung_wifi_client.py browse
python3 samsung_wifi_client.py download --dest downloads --new-only
```

If discovery fails but you know the camera IP:

```sh
python3 samsung_wifi_client.py --ip 192.168.0.225 browse
```

## DMS Database Fallback

Some Samsung modes expose a `config/DMS/media.db` SQLite index on the camera card. If you copied that file locally, the CLI can use it to build the media list:

```sh
python3 samsung_wifi_client.py --ip 192.168.0.225 db-list --db /path/to/config/DMS/media.db
python3 samsung_wifi_client.py --ip 192.168.0.225 db-download --db /path/to/config/DMS/media.db --dest downloads --new-only
```

This still only performs HTTP downloads from the camera.

## Safety

Nexus.cam is intentionally limited to media listing and download. Firmware modification and camera write operations are out of scope.

## Contributing

Want to help test another camera or improve the app? Open an issue, send a pull request, or email `njordblaviken@outlook.com`.

Compatibility reports for other Samsung SMART Camera models are especially useful.

## Troubleshooting

- Use `AllShare Play` / `Samsung Link`; Remote Viewfinder mode is not a file transfer mode.
- If discovery keeps searching, leave the camera on the pairing screen and accept any prompt.
- If Browse fails after a previous successful connection, restart the camera Wi-Fi mode and run Discover again.
- If Windows Firewall asks about Python or Nexus.cam, allow access on private networks.

## Project Files

- `samsung_wifi_web.py`: local browser UI and download server
- `samsung_wifi_client.py`: Samsung camera discovery, browsing, and transfer logic
- `nexus_cam.py`: desktop launcher for packaged builds
- `packaging/`: PyInstaller and Windows installer files
- `PACKAGING.md`: notes for building installer-style releases
