#!/usr/bin/env python3
"""
Read-only Wi-Fi client for Samsung SMART Camera media transfer.

This talks to the camera's built-in UPnP/DLNA ContentDirectory service.
It does not upload, delete, rename, or alter firmware.
"""

from __future__ import annotations

import argparse
import http.client
import html
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_REQUEST = "\r\n".join(
    [
        "M-SEARCH * HTTP/1.1",
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}",
        'MAN: "ssdp:discover"',
        "MX: 2",
        "ST: upnp:rootdevice",
        "",
        "",
    ]
)

SKIP_IP_PREFIXES = ("127.", "169.254.")
THUMBNAIL_MARKERS = ("JPEG_TN", "JPEG_SM", "PNG_TN", "PNG_SM", "_TN", "_SM")
MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/mpeg": ".mpg",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
    "video/3gpp": ".3gp",
}


@dataclass(frozen=True)
class Device:
    ip: str
    location: str
    server: str = ""


@dataclass(frozen=True)
class Camera:
    device: Device
    friendly_name: str
    manufacturer: str
    model_name: str
    model_number: str
    content_directory_url: str


@dataclass(frozen=True)
class MediaFile:
    title: str
    url: str
    size: int
    mime: str
    object_id: str = ""
    thumbnail_url: str = ""
    date: str = ""
    media_class: str = ""
    duration: str = ""
    resolution: str = ""


DEFAULT_DMS_DB = "config/DMS/media.db"


def local_ipv4_addresses() -> list[str]:
    ips: list[str] = []

    try:
        output = subprocess.check_output(["ifconfig"], text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            line = line.strip()
            if not line.startswith("inet "):
                continue
            ip = line.split()[1]
            if any(ip.startswith(prefix) for prefix in SKIP_IP_PREFIXES):
                continue
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if any(ip.startswith(prefix) for prefix in SKIP_IP_PREFIXES):
                continue
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    return ips or ["0.0.0.0"]


def local_ip_for_remote(remote_ip: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((remote_ip, 9))
        return sock.getsockname()[0]
    finally:
        sock.close()


def local_mac() -> str:
    value = uuid.getnode()
    return f"{value:012X}"


def discover(timeout: float = 5.0) -> list[Device]:
    devices: list[Device] = []
    seen_locations: set[str] = set()

    for local_ip in local_ipv4_addresses():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
            if local_ip != "0.0.0.0":
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
            sock.settimeout(timeout)
            sock.sendto(SSDP_REQUEST.encode("ascii"), (SSDP_ADDR, SSDP_PORT))

            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(8192)
                except socket.timeout:
                    break

                headers = parse_headers(data.decode("utf-8", errors="replace"))
                location = headers.get("location")
                if not location or location in seen_locations:
                    continue
                seen_locations.add(location)
                devices.append(Device(ip=addr[0], location=location, server=headers.get("server", "")))
        except OSError:
            continue
        finally:
            sock.close()

    return devices


def parse_headers(response: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in response.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def fetch_xml(url: str, timeout: float = 8.0) -> ET.Element:
    req = urllib.request.Request(url, headers={"User-Agent": "SamsungWifiClient/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return ET.fromstring(response.read())


def child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if strip_ns(child.tag) == name:
            return child.text or ""
    return ""


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def absolutize_url(base_url: str, maybe_relative: str) -> str:
    return urllib.parse.urljoin(base_url, maybe_relative)


def samsung_fallback_camera(device: Device) -> Optional[Camera]:
    marker_text = " ".join([device.location, device.server]).lower()
    if "samsung" not in marker_text and "smp_" not in marker_text:
        return None
    if "smp_2_" not in device.location:
        return None

    return Camera(
        device=device,
        friendly_name="Samsung Camera",
        manufacturer="Samsung",
        model_name="",
        model_number="",
        content_directory_url=device.location.replace("smp_2_", "smp_3_"),
    )


def camera_from_description(device: Device) -> Optional[Camera]:
    try:
        root = fetch_xml(device.location)
    except Exception:
        return samsung_fallback_camera(device)

    device_elem = next((elem for elem in root.iter() if strip_ns(elem.tag) == "device"), None)
    if device_elem is None:
        return None

    friendly_name = child_text(device_elem, "friendlyName")
    manufacturer = child_text(device_elem, "manufacturer")
    model_name = child_text(device_elem, "modelName")
    model_number = child_text(device_elem, "modelNumber")
    content_directory_url = ""

    for service in device_elem.iter():
        if strip_ns(service.tag) != "service":
            continue
        service_type = child_text(service, "serviceType")
        if "ContentDirectory" not in service_type:
            continue
        content_directory_url = absolutize_url(device.location, child_text(service, "controlURL"))
        break

    if not content_directory_url:
        return samsung_fallback_camera(device)

    name_bits = " ".join([friendly_name, manufacturer, model_name, device.server]).lower()
    looks_like_samsung_camera = (
        "samsung" in name_bits
        or "camera" in name_bits
        or "smp_" in device.location.lower()
    )
    if not looks_like_samsung_camera:
        return None

    return Camera(
        device=device,
        friendly_name=friendly_name,
        manufacturer=manufacturer,
        model_name=model_name,
        model_number=model_number,
        content_directory_url=content_directory_url,
    )


def find_camera(timeout: float = 5.0) -> Optional[Camera]:
    for device in discover(timeout=timeout):
        camera = camera_from_description(device)
        if camera:
            return camera
    return None


def camera_from_ip(ip: str, port: Optional[int] = None) -> Optional[Camera]:
    candidates = []
    if port:
        candidates.append(f"http://{ip}:{port}/smp_6_")
        candidates.append(f"http://{ip}:{port}/smp_2_")
        candidates.append(f"http://{ip}:{port}/description.xml")
        candidates.append(f"http://{ip}:{port}/rootDesc.xml")

    candidates.extend(
        [
            f"http://{ip}:7676/smp_6_",
            f"http://{ip}:7676/smp_2_",
            f"http://{ip}:5215/description.xml",
            f"http://{ip}:5215/rootDesc.xml",
            f"http://{ip}:49152/description.xml",
            f"http://{ip}:49153/description.xml",
            f"http://{ip}/description.xml",
            f"http://{ip}/rootDesc.xml",
        ]
    )

    for location in candidates:
        camera = camera_from_description(Device(ip=ip, location=location))
        if camera:
            return camera
    return None


def soap_browse(control_url: str, object_id: str, start: int = 0, count: int = 200) -> str:
    escaped_object_id = html.escape(object_id, quote=True)
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <ObjectID>{escaped_object_id}</ObjectID>
      <BrowseFlag>BrowseDirectChildren</BrowseFlag>
      <Filter>*</Filter>
      <StartingIndex>{start}</StartingIndex>
      <RequestedCount>{count}</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Browse>
  </s:Body>
</s:Envelope>"""
    body_bytes = body.encode("utf-8")
    variants = ['"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"']
    last_error: Optional[Exception] = None

    for soap_action in variants:
        try:
            response_body = http_post(control_url, body_bytes, soap_action)
            envelope = ET.fromstring(response_body)
            break
        except Exception as error:
            last_error = error
    else:
        raise RuntimeError(
            f"Browse failed for ObjectID={object_id!r}. Last error: {last_error}"
        )

    for elem in envelope.iter():
        if strip_ns(elem.tag) == "Result":
            return elem.text or ""
    return ""


def http_post(url: str, body: bytes, soap_action: str) -> bytes:
    status, reason, headers, data = http_post_raw(url, body, soap_action)
    if status >= 400:
        snippet = data[:300].decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {status} {reason}: {snippet}")
    if not data:
        raise RuntimeError(
            f"empty HTTP {status} response; camera may need a different Wi-Fi mode"
        )
    return data


def http_post_raw(url: str, body: bytes, soap_action: str) -> tuple[int, str, list[tuple[str, str]], bytes]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=15)
    try:
        connection.putrequest("POST", path, skip_accept_encoding=True)
        connection.putheader("Host", parsed.netloc)
        connection.putheader("Content-Type", 'text/xml; charset="utf-8"')
        connection.putheader("SOAPAction", soap_action)
        connection.putheader("User-Agent", "SamsungWifiClient/1.0")
        connection.putheader("Connection", "close")
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        try:
            data = response.read()
        except http.client.IncompleteRead as error:
            data = error.partial

        return response.status, response.reason, response.getheaders(), data
    finally:
        connection.close()


def parse_didl(didl_xml: str) -> tuple[list[tuple[str, str]], list[MediaFile]]:
    containers: list[tuple[str, str]] = []
    files: list[MediaFile] = []
    if not didl_xml:
        return containers, files

    root = ET.fromstring(didl_xml)
    for elem in root:
        tag = strip_ns(elem.tag)
        if tag == "container":
            containers.append((elem.attrib.get("id", ""), child_text(elem, "title")))
        elif tag == "item":
            title = child_text(elem, "title")
            date = child_text(elem, "date")
            media_class = child_text(elem, "class")
            object_id = elem.attrib.get("id", "")
            resources = []
            for child in elem:
                if strip_ns(child.tag) != "res" or not child.text:
                    continue
                protocol_info = child.attrib.get("protocolInfo", "")
                mime = protocol_info.split(":")[2] if protocol_info.count(":") >= 2 else ""
                size = int(child.attrib.get("size") or 0)
                resources.append(
                    {
                        "url": child.text,
                        "size": size,
                        "mime": mime,
                        "protocol_info": protocol_info,
                        "duration": child.attrib.get("duration", ""),
                        "resolution": child.attrib.get("resolution", ""),
                    }
                )
            if resources:
                full_size = [
                    item
                    for item in resources
                    if not any(marker in item["protocol_info"] for marker in THUMBNAIL_MARKERS)
                ]
                thumbnails = [
                    item
                    for item in resources
                    if any(marker in item["protocol_info"] for marker in THUMBNAIL_MARKERS)
                ]
                best = max(full_size or resources, key=lambda item: item["size"])
                thumbnail = min(thumbnails, key=lambda item: item["size"]) if thumbnails else None
                files.append(
                    MediaFile(
                        title=title,
                        url=best["url"],
                        size=best["size"],
                        mime=best["mime"],
                        object_id=object_id,
                        thumbnail_url=thumbnail["url"] if thumbnail else "",
                        date=date,
                        media_class=media_class,
                        duration=best.get("duration", ""),
                        resolution=best.get("resolution", ""),
                    )
                )

    return containers, files


def browse_recursive(control_url: str, object_id: str = "0", path: str = "") -> list[MediaFile]:
    didl = soap_browse(control_url, object_id)
    containers, files = parse_didl(didl)
    found: list[MediaFile] = []

    for media in files:
        title = "/".join(part for part in [path, media.title] if part)
        found.append(
            MediaFile(
                title=title,
                url=media.url,
                size=media.size,
                mime=media.mime,
                object_id=media.object_id,
                thumbnail_url=media.thumbnail_url,
                date=media.date,
                media_class=media.media_class,
                duration=media.duration,
                resolution=media.resolution,
            )
        )

    for child_id, child_title in containers:
        if not child_id:
            continue
        child_path = "/".join(part for part in [path, child_title] if part)
        found.extend(browse_recursive(control_url, child_id, child_path))

    return found


def browse_camera(camera: Camera) -> list[MediaFile]:
    errors = []
    for object_id in ("0", "5"):
        try:
            files = browse_recursive(camera.content_directory_url, object_id)
        except Exception as error:
            errors.append(f"ObjectID {object_id}: {error}")
            continue
        if files:
            return files
    if errors:
        raise RuntimeError("Browse failed:\n" + "\n".join(errors))
    return []


def get_url(url: str) -> tuple[int, str, list[tuple[str, str]], bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "SamsungWifiClient/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.status, response.reason, response.getheaders(), response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.reason, list(error.headers.items()), error.read()


def print_response_summary(label: str, status: int, reason: str, headers: list[tuple[str, str]], data: bytes) -> None:
    content_type = next((value for key, value in headers if key.lower() == "content-type"), "")
    content_length = next((value for key, value in headers if key.lower() == "content-length"), "")
    print(f"{label}: HTTP {status} {reason}, bytes={len(data)}, content-length={content_length}, type={content_type}")
    if data:
        preview = data[:500].decode("utf-8", errors="replace").replace("\r", "")
        print(preview)
        if len(data) > 500:
            print("...")


def soap_action(
    control_url: str,
    service_type: str,
    action: str,
    arguments: dict[str, str],
) -> bytes:
    args_xml = "".join(
        f"<{name}>{html.escape(value, quote=True)}</{name}>"
        for name, value in arguments.items()
    )
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="{service_type}">
      {args_xml}
    </u:{action}>
  </s:Body>
</s:Envelope>""".encode("utf-8")
    return http_post(control_url, body, f'"{service_type}#{action}"')


def safe_filename(name: str, mime: str, url: str) -> str:
    name = name.strip().replace("\\", "/").split("/")[-1] or "camera_file"
    name = re.sub(r"[\x00-\x1f:]", "_", name)
    if "." not in name:
        ext = MIME_EXT.get(mime.lower())
        if not ext:
            parsed_path = urllib.parse.urlparse(url).path
            suffix = Path(parsed_path).suffix
            ext = suffix if suffix else ""
        name += ext
    return name


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 10000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique filename for {path}")


def download(files: list[MediaFile], dest: Path, new_only: bool, keep_going: bool = False) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    total = len(files)
    failures = 0
    for index, media in enumerate(files, 1):
        filename = safe_filename(media.title, media.mime, media.url)
        target = dest / filename

        if target.exists() and (not media.size or target.stat().st_size == media.size):
            print(f"[{index}/{total}] exists  {filename}", flush=True)
            continue
        if target.exists() and new_only:
            print(f"[{index}/{total}] skip    {filename}", flush=True)
            continue
        if target.exists():
            target = unique_path(target)

        print(f"[{index}/{total}] get     {target.name}", flush=True)
        tmp = target.with_suffix(target.suffix + ".part")
        try:
            urllib.request.urlretrieve(media.url, tmp)
            os.replace(tmp, target)
        except Exception as error:
            if tmp.exists():
                tmp.unlink()
            if not keep_going:
                raise
            failures += 1
            print(f"    error   {error}", flush=True)
    if failures:
        raise SystemExit(f"{failures} download(s) failed.")


def filename_from_full_path(path: str, title: str) -> str:
    name = Path(path.replace("\\", "/")).name
    if name:
        return name
    return title


def files_from_dms_db(db_path: Path, ip: str, port: int = 7676) -> list[MediaFile]:
    if not db_path.exists():
        raise SystemExit(f"DMS database not found: {db_path}")

    files: list[MediaFile] = []
    base_url = f"http://{ip}:{port}"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        for table in ("ImageTable", "VideoTable"):
            rows = connection.execute(
                f"""
                SELECT id, Title, size, FullPath, MimeType, uri, Thumbnailuri, date
                FROM {table}
                WHERE uri IS NOT NULL AND uri != ''
                ORDER BY CAST(id AS INTEGER)
                """
            )
            for row in rows:
                filename = filename_from_full_path(row["FullPath"], row["Title"])
                files.append(
                    MediaFile(
                        title=filename,
                        url=urllib.parse.urljoin(base_url, row["uri"]),
                        size=int(row["size"] or 0),
                        mime=row["MimeType"] or "",
                        object_id=str(row["id"]),
                        thumbnail_url=urllib.parse.urljoin(base_url, row["Thumbnailuri"]) if "Thumbnailuri" in row.keys() and row["Thumbnailuri"] else "",
                        date=row["date"] or "",
                    )
                )
    return files


def head_or_get(url: str, timeout: float = 3.0) -> tuple[int, str, list[tuple[str, str]], bytes]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "/"
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)
    try:
        connection.request("HEAD", path, headers={"Connection": "close", "User-Agent": "SamsungWifiClient/1.0"})
        response = connection.getresponse()
        response.read()
        headers = response.getheaders()
        if response.status not in (400, 405, 501):
            return response.status, response.reason, headers, b""
    except Exception:
        pass
    finally:
        connection.close()

    req = urllib.request.Request(url, headers={"User-Agent": "SamsungWifiClient/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.reason, response.getheaders(), response.read(512)
    except urllib.error.HTTPError as error:
        return error.code, error.reason, list(error.headers.items()), error.read(512)


def db_diagnostic_urls(files: list[MediaFile], ip: str, ports: list[int], sample_count: int) -> list[str]:
    sample_paths = []
    for media in files[:sample_count]:
        sample_paths.append(urllib.parse.urlparse(media.url).path)

    static_paths = [
        "/smp_2_",
        "/smp_3_",
        "/smp_10_",
        "/smp_11_",
        "/config/DMS/media.db",
    ]
    paths = sample_paths + [path for path in static_paths if path not in sample_paths]
    return [f"http://{ip}:{port}{path}" for port in ports for path in paths]


def resolve_camera(args: argparse.Namespace) -> Camera:
    if args.ip:
        camera = camera_from_ip(args.ip, args.port)
    else:
        camera = find_camera(timeout=args.timeout)
    if not camera:
        raise SystemExit(
            "No Samsung camera found. Put the camera in MobileLink, AutoShare, or Samsung Link/DLNA mode, "
            "connect this computer to the same Wi-Fi network, then retry. You can also pass --ip CAMERA_IP."
        )
    return camera


def print_camera(camera: Camera) -> None:
    print(f"Name:   {camera.friendly_name}")
    print(f"Maker:  {camera.manufacturer}")
    print(f"Model:  {camera.model_name} {camera.model_number}".rstrip())
    print(f"IP:     {camera.device.ip}")
    print(f"UPnP:   {camera.content_directory_url}")


def cmd_discover(args: argparse.Namespace) -> None:
    devices = discover(timeout=args.timeout)
    if not devices:
        print("No UPnP devices found.")
        return

    for device in devices:
        camera = camera_from_description(device)
        if camera:
            print_camera(camera)
            print()
        else:
            print(f"Device: {device.ip}  {device.location}  {device.server}")


def cmd_browse(args: argparse.Namespace) -> None:
    camera = resolve_camera(args)
    print_camera(camera)
    print()
    try:
        files = browse_camera(camera)
    except RuntimeError as error:
        raise SystemExit(
            f"{error}\n\n"
            "The camera is reachable, but this Wi-Fi mode is not returning a media directory. "
            "On the WB200F, try a photo-sharing/DLNA mode such as MobileLink, AutoShare, "
            "or Samsung Link/AllShare Play rather than Remote Viewfinder. "
            "Run `python3 samsung_wifi_client.py diagnostics` while connected to the camera Wi-Fi "
            "if you want the raw service diagnostics."
        )
    for media in files:
        size_kb = media.size // 1024 if media.size else 0
        print(f"{media.title}\t{size_kb} KB\t{media.mime}")
    print(f"\n{len(files)} file(s)")


def cmd_download(args: argparse.Namespace) -> None:
    camera = resolve_camera(args)
    print_camera(camera)
    print()
    try:
        files = browse_camera(camera)
    except RuntimeError as error:
        raise SystemExit(
            f"{error}\n\n"
            "The camera is reachable, but this Wi-Fi mode is not returning a media directory. "
            "Switch the camera to a photo-sharing/DLNA mode, then retry."
        )
    if not files:
        print("No downloadable media found.")
        return
    download(files, Path(args.dest).expanduser(), new_only=args.new_only)


def cmd_db_list(args: argparse.Namespace) -> None:
    files = files_from_dms_db(Path(args.db).expanduser(), args.ip, args.http_port)
    total = sum(media.size for media in files)
    for media in files:
        size_kb = media.size // 1024 if media.size else 0
        print(f"{media.title}\t{size_kb} KB\t{media.mime}\t{media.url}")
    print(f"\n{len(files)} file(s), {total // 1024 // 1024} MB indexed by DMS media.db")


def cmd_db_download(args: argparse.Namespace) -> None:
    files = files_from_dms_db(Path(args.db).expanduser(), args.ip, args.http_port)
    if not files:
        print("No files indexed in DMS media.db.")
        return
    download(files, Path(args.dest).expanduser(), new_only=args.new_only, keep_going=args.keep_going)


def cmd_db_diagnostics(args: argparse.Namespace) -> None:
    files = files_from_dms_db(Path(args.db).expanduser(), args.ip, args.http_port)
    if not files:
        print("No files indexed in DMS media.db.")
        return
    ports = [int(part) for part in args.ports.split(",") if part.strip()]
    for url in db_diagnostic_urls(files, args.ip, ports, args.samples):
        try:
            status, reason, headers, data = head_or_get(url, timeout=args.request_timeout)
            content_type = next((value for key, value in headers if key.lower() == "content-type"), "")
            content_length = next((value for key, value in headers if key.lower() == "content-length"), "")
            print(f"{status}\t{reason}\tbytes={len(data)}\tlen={content_length}\ttype={content_type}\t{url}")
        except Exception as error:
            print(f"ERR\t{error}\t{url}")


def cmd_diagnostics(args: argparse.Namespace) -> None:
    camera = resolve_camera(args)
    print_camera(camera)
    print()

    for label, url in [
        ("device description", camera.device.location),
        ("content directory SCPD guess", camera.content_directory_url.replace("smp_3_", "smp_5_")),
        ("connection manager SCPD guess", camera.content_directory_url.replace("smp_3_", "smp_8_")),
    ]:
        try:
            print_response_summary(label, *get_url(url))
        except Exception as error:
            print(f"{label}: {error}")
        print()

    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
      <ObjectID>0</ObjectID>
      <BrowseFlag>BrowseDirectChildren</BrowseFlag>
      <Filter>*</Filter>
      <StartingIndex>0</StartingIndex>
      <RequestedCount>20</RequestedCount>
      <SortCriteria></SortCriteria>
    </u:Browse>
  </s:Body>
</s:Envelope>""".encode("utf-8")

    for action in [
        '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
        "urn:schemas-upnp-org:service:ContentDirectory:1#Browse",
    ]:
        try:
            print_response_summary(f"SOAP Browse action={action}", *http_post_raw(camera.content_directory_url, body, action))
        except Exception as error:
            print(f"SOAP Browse action={action}: {error}")
        print()


def cmd_pair(args: argparse.Namespace) -> None:
    camera = resolve_camera(args)
    ip = camera.device.ip
    host_ip = args.host_ip or local_ip_for_remote(ip)
    mac = (args.mac or local_mac()).replace(":", "").replace("-", "").upper()
    url = f"http://{ip}:7788/mode/control"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"SEC_MODE_{mac}",
            "HOST-Mac": mac,
            "HOST-Address": host_ip,
            "Connection": "close",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            headers = response.getheaders()
            status = response.status
            reason = response.reason
    except urllib.error.HTTPError as error:
        data = error.read()
        headers = list(error.headers.items())
        status = error.code
        reason = error.reason

    print(f"Pair/control request sent to {url}")
    print(f"HOST-Address: {host_ip}")
    print(f"HOST-Mac:     {mac}")
    print_response_summary("mode/control", status, reason, headers, data)
    print()
    print("If the camera showed a prompt, accept it, then retry `python3 samsung_wifi_client.py browse`.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Samsung SMART Camera Wi-Fi transfer client")
    parser.add_argument("--ip", help="Camera IP address if discovery fails")
    parser.add_argument("--port", type=int, help="Optional camera description port for --ip")
    parser.add_argument("--timeout", type=float, default=5.0, help="SSDP discovery timeout in seconds")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover", help="Find Samsung cameras and other UPnP devices")
    sub.add_parser("browse", help="List camera media without downloading")
    sub.add_parser("diagnostics", aliases=["probe"], help="Inspect the advertised Wi-Fi media service")
    pair_parser = sub.add_parser("pair", help="Send Samsung Remote Viewfinder pairing/control request")
    pair_parser.add_argument("--host-ip", help="Local computer IP on the camera Wi-Fi, if auto-detection is wrong")
    pair_parser.add_argument("--mac", help="Local MAC address to present, without separators")
    download_parser = sub.add_parser("download", help="Download camera media over HTTP")
    download_parser.add_argument("--dest", default="downloads", help="Destination folder")
    download_parser.add_argument("--new-only", action="store_true", help="Skip names that already exist locally")
    db_list_parser = sub.add_parser("db-list", help="List media using a copied Samsung DMS media.db index")
    db_list_parser.add_argument("--db", default=DEFAULT_DMS_DB, help="Path to config/DMS/media.db from a copied camera card")
    db_list_parser.add_argument("--http-port", type=int, default=7676, help="Camera HTTP media port")
    db_diag_parser = sub.add_parser("db-diagnostics", aliases=["db-probe"], help="Inspect DMS media URLs and service endpoints")
    db_diag_parser.add_argument("--db", default=DEFAULT_DMS_DB, help="Path to config/DMS/media.db from a copied camera card")
    db_diag_parser.add_argument("--http-port", type=int, default=7676, help="Port used when building media URLs from the DB")
    db_diag_parser.add_argument("--ports", default="7676,5215", help="Comma-separated ports to inspect")
    db_diag_parser.add_argument("--samples", type=int, default=1, help="Number of indexed media URLs to inspect per port")
    db_diag_parser.add_argument("--request-timeout", type=float, default=3.0, help="Timeout per diagnostic request")
    db_download_parser = sub.add_parser("db-download", help="Download media using a copied Samsung DMS media.db index")
    db_download_parser.add_argument("--db", default=DEFAULT_DMS_DB, help="Path to config/DMS/media.db from a copied camera card")
    db_download_parser.add_argument("--http-port", type=int, default=7676, help="Camera HTTP media port")
    db_download_parser.add_argument("--dest", default="downloads-db", help="Destination folder")
    db_download_parser.add_argument("--new-only", action="store_true", help="Skip names that already exist locally")
    db_download_parser.add_argument("--keep-going", action="store_true", help="Continue after individual download failures")

    args = parser.parse_args()
    if args.command == "discover":
        cmd_discover(args)
    elif args.command == "browse":
        cmd_browse(args)
    elif args.command in ("diagnostics", "probe"):
        cmd_diagnostics(args)
    elif args.command == "pair":
        cmd_pair(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "db-list":
        if not args.ip:
            raise SystemExit("db-list needs --ip CAMERA_IP, for example --ip 192.168.102.1")
        cmd_db_list(args)
    elif args.command in ("db-diagnostics", "db-probe"):
        if not args.ip:
            raise SystemExit("db-diagnostics needs --ip CAMERA_IP, for example --ip 192.168.102.1")
        cmd_db_diagnostics(args)
    elif args.command == "db-download":
        if not args.ip:
            raise SystemExit("db-download needs --ip CAMERA_IP, for example --ip 192.168.102.1")
        cmd_db_download(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
