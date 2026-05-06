#!/usr/bin/env python3
"""
Local web UI for Nexus.cam.

Run:
  python3 samsung_wifi_web.py

Then open:
  http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import samsung_wifi_client as camera_client


HOST = "127.0.0.1"
PORT = 8765
APP_NAME = "Nexus.cam"
APP_VERSION = "0.1.0"
APP_TAGLINE = "i fixed what samsung broke"
DEFAULT_DEST = str(Path.home() / "Pictures" / "SamsungCamera")

MEDIA_CACHE: dict[str, list[camera_client.MediaFile]] = {}
JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nexus.cam</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #11100e;
      --panel: #1d1b17;
      --panel-2: #141310;
      --ink: #f0eadf;
      --muted: #9c9487;
      --line: #d8cfbf;
      --line-2: #39352d;
      --accent: #d7ff4f;
      --accent-2: #ff6b35;
      --accent-soft: rgba(215, 255, 79, .14);
      --ok: #35d07f;
      --warn: #f7d047;
      --bad: #ff4d4d;
      --radius: 0px;
      --shadow: 5px 5px 0 #050505;
      --font: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }
    body[data-theme="brutal"] {
      --bg: #11100e;
      --panel: #1d1b17;
      --panel-2: #141310;
      --ink: #f0eadf;
      --muted: #9c9487;
      --line: #d8cfbf;
      --line-2: #39352d;
      --accent: #d7ff4f;
      --accent-2: #b6a98f;
      --accent-soft: rgba(215, 255, 79, .14);
    }
    body[data-theme="oxide"] {
      --bg: #120f0d;
      --panel: #211a16;
      --panel-2: #17120f;
      --ink: #f1e7dc;
      --muted: #a88f7d;
      --line: #d2b9a5;
      --line-2: #49352b;
      --accent: #ff7a3d;
      --accent-2: #ffc857;
      --accent-soft: rgba(255, 122, 61, .16);
    }
    body[data-theme="cobalt"] {
      --bg: #0c1020;
      --panel: #151b30;
      --panel-2: #0d1324;
      --ink: #e6edf7;
      --muted: #8f9bb3;
      --line: #b9c7ea;
      --line-2: #2d3758;
      --accent: #73a7ff;
      --accent-2: #d7ff73;
      --accent-soft: rgba(115, 167, 255, .18);
    }
    body[data-theme="mono"] {
      --bg: #0b0b0b;
      --panel: #191919;
      --panel-2: #111;
      --ink: #efefef;
      --muted: #9a9a9a;
      --line: #dcdcdc;
      --line-2: #333;
      --accent: #efefef;
      --accent-2: #bdbdbd;
      --accent-soft: rgba(255, 255, 255, .12);
    }
    body[data-theme="crt"] {
      --bg: #06110a;
      --panel: #0a1a10;
      --panel-2: #06150b;
      --ink: #d5ffe5;
      --muted: #75b987;
      --line: #27824a;
      --line-2: #123c24;
      --accent: #55ff88;
      --accent-2: #ffec70;
      --accent-soft: rgba(50, 255, 126, .18);
      --shadow: 0 0 0 1px #123c24, 0 0 22px rgba(50, 255, 126, .08);
    }
    body[data-theme="zine"] {
      color-scheme: light;
      --bg: #ede5d0;
      --panel: #fbf4e2;
      --panel-2: #e7dcc2;
      --ink: #161616;
      --muted: #5b554b;
      --line: #161616;
      --line-2: #b8aa8e;
      --accent: #2848ff;
      --accent-2: #d94b22;
      --accent-soft: rgba(0, 87, 255, .16);
      --ok: #096b31;
      --warn: #8a5a00;
      --bad: #b42318;
      --shadow: 5px 5px 0 #161616;
    }
    body[data-theme="hacker"] {
      --bg: #050507;
      --panel: #101014;
      --panel-2: #08080b;
      --ink: #e8e8ea;
      --muted: #888895;
      --line: #30303a;
      --line-2: #1b1b22;
      --accent: #c6ff54;
      --accent-2: #8b78ff;
      --accent-soft: rgba(183, 255, 42, .15);
      --shadow: none;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 13px/1.45 var(--font);
      color: var(--ink);
      background: var(--bg);
    }
    body[data-theme="crt"]::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background: repeating-linear-gradient(to bottom, rgba(255,255,255,.03), rgba(255,255,255,.03) 1px, transparent 1px, transparent 4px);
      mix-blend-mode: screen;
      opacity: .45;
      z-index: 20;
    }
    header {
      padding: 12px 16px;
      border-bottom: 2px solid var(--line);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 15px;
      font-weight: 900;
      letter-spacing: .02em;
      text-transform: uppercase;
    }
    .brand { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
    .icon-btn {
      width: 34px;
      height: 34px;
      padding: 0;
      display: inline-grid;
      place-items: center;
    }
    .icon-btn svg,
    .folder-link svg {
      width: 18px;
      height: 18px;
      stroke: currentColor;
      fill: none;
      stroke-width: 2;
      stroke-linecap: square;
      stroke-linejoin: miter;
    }
    .settings-layer {
      position: fixed;
      inset: 0;
      z-index: 30;
      background: rgba(0, 0, 0, .52);
      display: none;
      align-items: flex-start;
      justify-content: flex-end;
      padding: 62px 16px 16px;
    }
    .settings-layer.open { display: flex; }
    .settings-window {
      width: min(420px, calc(100vw - 32px));
      background: var(--panel);
      border: 2px solid var(--line);
      box-shadow: var(--shadow);
    }
    .settings-head {
      padding: 9px 11px;
      border-bottom: 2px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .settings-body {
      padding: 12px;
      display: grid;
      gap: 14px;
    }
    .settings-divider {
      border: 0;
      border-top: 2px solid var(--line-2);
      width: 100%;
      margin: 2px 0;
    }
    .about-box {
      display: grid;
      gap: 8px;
      border: 2px solid var(--line-2);
      background: var(--panel-2);
      padding: 10px;
      color: var(--muted);
      text-transform: none;
      letter-spacing: 0;
      font-weight: 700;
    }
    .about-box strong {
      color: var(--ink);
      text-transform: uppercase;
      letter-spacing: .02em;
    }
    .about-grid {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 4px 10px;
      font-size: 12px;
    }
    .theme-grid {
      display: grid;
      grid-template-columns: repeat(6, 34px);
      gap: 8px;
    }
    .theme-btn {
      width: 34px;
      height: 34px;
      padding: 0;
      display: grid;
      place-items: center;
      border-color: var(--line);
      color: #080808;
      box-shadow: inset 0 -10px 0 rgba(0, 0, 0, .18);
    }
    .theme-btn[data-theme="brutal"] { background: #d7ff4f; }
    .theme-btn[data-theme="oxide"] { background: #ff7a3d; }
    .theme-btn[data-theme="cobalt"] { background: #73a7ff; }
    .theme-btn[data-theme="mono"] { background: #efefef; }
    .theme-btn[data-theme="crt"] { background: #55ff88; }
    .theme-btn[data-theme="zine"] { background: #2848ff; color: #fff; }
    .theme-btn.active { outline: 3px solid var(--accent); outline-offset: 2px; }
    .settings-link {
      border: 2px solid var(--line-2);
      background: var(--panel-2);
      padding: 9px 10px;
      color: var(--muted);
      text-transform: none;
      letter-spacing: 0;
      font-size: 12px;
      font-weight: 800;
    }
    .settings-link a {
      color: var(--accent);
      text-transform: uppercase;
      text-decoration: none;
      border-bottom: 2px solid currentColor;
    }
    .settings-link a:hover {
      color: var(--accent-2);
    }
    main {
      padding: 16px;
      display: grid;
      grid-template-columns: minmax(280px, 0.32fr) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    body.connected main {
      grid-template-columns: 1fr;
      padding-top: 68px;
    }
    section {
      background: var(--panel);
      border: 2px solid var(--line);
      border-radius: var(--radius);
      overflow: hidden;
      box-shadow: var(--shadow);
    }
    .section-head {
      padding: 9px 11px;
      border-bottom: 2px solid var(--line);
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .02em;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .section-body { padding: 12px; }
    .stack { display: grid; gap: 12px; }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .connection-panel {
      position: sticky;
      top: 14px;
      z-index: 10;
      transition: transform 220ms ease, width 220ms ease, box-shadow 220ms ease;
    }
    body:not(.connected) .connection-panel {
      position: fixed;
      left: 50%;
      top: 48%;
      width: min(440px, calc(100vw - 32px));
      transform: translate(-50%, -50%);
    }
    body:not(.connected) main {
      min-height: calc(100vh - 55px);
      display: block;
    }
    body:not(.connected) main > section:not(.connection-panel) {
      display: none;
    }
    body.connected .connection-panel {
      position: fixed;
      left: 16px;
      top: 64px;
      width: 188px;
      box-shadow: 4px 4px 0 #000;
    }
    body.connected .connection-panel .section-head {
      border-bottom: 0;
      cursor: default;
    }
    body.connected .connection-panel .section-head::after {
      content: "CONNECTED";
      color: #000;
      background: var(--accent);
      padding: 1px 5px;
      margin-left: auto;
    }
    body.connected .connection-panel .section-body {
      display: none;
    }
    body.connected .connection-panel:hover,
    body.connected .connection-panel:focus-within {
      width: 340px;
    }
    body.connected .connection-panel:hover .section-head,
    body.connected .connection-panel:focus-within .section-head {
      border-bottom: 2px solid var(--line);
    }
    body.connected .connection-panel:hover .section-body,
    body.connected .connection-panel:focus-within .section-body {
      display: grid;
    }
    label,
    .setting-field { display: grid; gap: 6px; color: var(--muted); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .02em; }
    input[type="text"] {
      width: 100%;
      border: 2px solid var(--line);
      border-radius: var(--radius);
      padding: 8px 9px;
      font: inherit;
      color: var(--ink);
      background: var(--bg);
      outline: none;
    }
    input[type="text"]:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
    button {
      border: 2px solid var(--line);
      background: var(--line-2);
      color: var(--ink);
      border-radius: var(--radius);
      padding: 7px 10px;
      font: inherit;
      font-weight: 900;
      cursor: pointer;
      text-transform: uppercase;
      letter-spacing: .01em;
    }
    button:hover { background: var(--accent-2); color: #000; }
    button.primary { border-color: var(--line); background: var(--accent); color: #000; }
    button.primary:hover { background: var(--accent-2); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .status {
      padding: 9px 10px;
      border-radius: var(--radius);
      background: var(--panel-2);
      border: 2px solid var(--line-2);
      color: var(--muted);
      min-height: 40px;
      white-space: pre-wrap;
    }
    .status.ok { color: var(--ok); background: rgba(46, 160, 67, .10); border-color: rgba(46, 160, 67, .25); }
    .status.bad { color: var(--bad); background: rgba(248, 81, 73, .10); border-color: rgba(248, 81, 73, .25); }
    .status.warn { color: var(--warn); background: rgba(210, 153, 34, .10); border-color: rgba(210, 153, 34, .25); }
    .camera-list { display: grid; gap: 8px; }
    .camera {
      border: 2px solid var(--line-2);
      border-radius: var(--radius);
      padding: 10px;
      display: grid;
      gap: 3px;
      cursor: pointer;
      background: var(--panel-2);
    }
    .camera:hover { border-color: var(--line); }
    .camera.active { border-color: var(--accent); box-shadow: inset 5px 0 0 var(--accent); }
    .muted { color: var(--muted); }
    .tiny { font-size: 12px; }
    .toolbar {
      display: grid;
      grid-template-columns: auto minmax(180px, 1fr) auto;
      gap: 10px;
      align-items: end;
    }
    .toolbar .row { align-items: end; }
    .media-tools {
      display: grid;
      grid-template-columns: 1fr;
      gap: 7px;
    }
    select {
      border: 2px solid var(--line);
      border-radius: var(--radius);
      background: var(--bg);
      color: var(--ink);
      padding: 8px 9px;
      font: inherit;
      font-weight: 900;
      text-transform: uppercase;
      outline: none;
    }
    .media-control-bar {
      display: grid;
      grid-template-columns: minmax(180px, 1fr) 180px auto;
      gap: 10px;
      align-items: end;
    }
    .view-switch {
      display: flex;
      gap: 6px;
      align-items: end;
      justify-content: flex-end;
    }
    .view-btn.active {
      background: var(--accent);
      color: #000;
    }
    .media-wrap {
      max-height: calc(100vh - 310px);
      overflow: auto;
    }
    .media-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
      gap: 12px;
    }
    .media-grid.view-compact {
      grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
      gap: 8px;
    }
    .media-grid.view-large {
      grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
      gap: 14px;
    }
    .media-grid.view-list {
      grid-template-columns: 1fr;
      gap: 6px;
    }
    .media-card {
      border: 2px solid var(--line-2);
      border-radius: var(--radius);
      overflow: hidden;
      background: var(--panel-2);
      cursor: pointer;
      position: relative;
    }
    .view-list .media-card {
      display: grid;
      grid-template-columns: 78px minmax(0, 1fr);
      align-items: stretch;
    }
    .media-card:hover { border-color: var(--line); }
    .media-card.selected { border-color: var(--accent); box-shadow: inset 0 -4px 0 var(--accent); }
    .thumb {
      width: 100%;
      aspect-ratio: 4 / 3;
      background: #010409;
      display: grid;
      place-items: center;
      overflow: hidden;
    }
    .view-compact .thumb { aspect-ratio: 1 / 1; }
    .view-large .thumb { aspect-ratio: 4 / 3; }
    .view-list .thumb {
      width: 78px;
      height: 58px;
      aspect-ratio: auto;
    }
    .thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      filter: saturate(.95) contrast(1.02);
    }
    body[data-theme="crt"] .thumb img { filter: grayscale(.25) contrast(1.15) brightness(.85); }
    body[data-theme="zine"] .thumb img { filter: grayscale(1) contrast(1.25); }
    body[data-theme="hacker"] .thumb img { filter: contrast(1.08) saturate(.8); }
    .thumb .placeholder { color: var(--muted); font-weight: 700; font-size: 12px; }
    .card-meta {
      padding: 8px;
      display: grid;
      gap: 2px;
      min-width: 0;
    }
    .view-list .card-meta {
      align-content: center;
      grid-template-columns: minmax(0, 1fr) auto;
      column-gap: 12px;
    }
    .card-name {
      font-weight: 900;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      text-transform: uppercase;
    }
    .card-sub { color: var(--muted); font-size: 12px; }
    .card-extra { color: var(--muted); font-size: 11px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    .view-compact .card-extra { display: none; }
    .media-card input {
      position: absolute;
      top: 7px;
      left: 7px;
      width: 18px;
      height: 18px;
      margin: 0;
      accent-color: var(--accent);
    }
    progress {
      display: none;
    }
    .progress-group {
      display: grid;
      gap: 7px;
    }
    .progress-row {
      display: grid;
      grid-template-columns: 94px minmax(0, 1fr) 72px;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
    }
    .progress-shell {
      border: 2px solid var(--line);
      background: var(--panel-2);
      height: 18px;
      position: relative;
      overflow: hidden;
    }
    .progress-fill {
      width: 0%;
      height: 100%;
      background: var(--accent);
      transition: width 260ms ease;
    }
    .folder-link {
      border: 0;
      background: transparent;
      color: var(--muted);
      padding: 0;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      justify-content: flex-start;
      text-transform: none;
      font-weight: 800;
      min-width: 0;
    }
    .folder-link:hover {
      background: transparent;
      color: var(--accent);
    }
    .folder-link span {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      body.connected main { padding-top: 120px; }
      .media-wrap { max-height: none; }
      header { align-items: flex-start; flex-direction: column; }
      .connection-panel { position: static; }
      body.connected .connection-panel,
      body.connected .connection-panel:hover,
      body.connected .connection-panel:focus-within {
        position: static;
        width: auto;
        transform: none;
      }
      body.connected .connection-panel .section-body { display: grid; }
      .toolbar,
      .media-control-bar { grid-template-columns: 1fr; }
      .view-switch { justify-content: flex-start; }
      .settings-layer { justify-content: center; }
    }
  </style>
</head>
<body data-theme="concrete">
  <header>
    <div class="brand">
      <h1>__APP_NAME__</h1>
      <div class="muted tiny">__APP_TAGLINE__</div>
    </div>
    <button class="icon-btn" id="settingsBtn" aria-label="Settings" title="Settings">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7Z"></path>
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3a1.7 1.7 0 0 0-1 1.6V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6a1.7 1.7 0 0 0-1.9.3l-.1.1A2 2 0 0 1 4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9a1.7 1.7 0 0 0-1.6-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.6-1.1A1.7 1.7 0 0 0 4.4 7l-.1-.1A2 2 0 0 1 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.6V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1.1 1.6a1.7 1.7 0 0 0 1.9-.3l.1-.1A2 2 0 0 1 19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.6 1h.1a2 2 0 0 1 0 4H21a1.7 1.7 0 0 0-1.6 1Z"></path>
      </svg>
    </button>
  </header>
  <div class="settings-layer" id="settingsLayer" aria-hidden="true">
    <div class="settings-window" role="dialog" aria-modal="true" aria-labelledby="settingsTitle">
      <div class="settings-head">
        <span id="settingsTitle">Settings</span>
        <button class="icon-btn" id="settingsCloseBtn" aria-label="Close settings" title="Close">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 6l12 12"></path>
            <path d="M18 6L6 18"></path>
          </svg>
        </button>
      </div>
      <div class="settings-body">
        <div class="setting-field">Theme
          <div class="theme-grid" aria-label="Theme">
            <button class="theme-btn active" data-theme="brutal" aria-label="Theme 1">1</button>
            <button class="theme-btn" data-theme="oxide" aria-label="Theme 2">2</button>
            <button class="theme-btn" data-theme="cobalt" aria-label="Theme 3">3</button>
            <button class="theme-btn" data-theme="mono" aria-label="Theme 4">4</button>
            <button class="theme-btn" data-theme="crt" aria-label="Theme 5">5</button>
            <button class="theme-btn" data-theme="zine" aria-label="Theme 6">6</button>
          </div>
        </div>
        <div class="settings-link">
          wanna contribute to this project?
          <a href="https://github.com/enverUslu/nexus-cam" target="_blank" rel="noreferrer">join here</a>
        </div>
        <label>Download folder
          <input id="destInput" type="text">
        </label>
        <hr class="settings-divider">
        <div class="setting-field">About
          <div class="about-box">
            <strong>__APP_NAME__ v__APP_VERSION__</strong>
            <div>Read-only media transfer for Samsung Wi-Fi cameras.</div>
            <div class="about-grid">
              <span>Network</span><span>Local browser app running at 127.0.0.1</span>
              <span>Camera</span><span>SSDP, UPnP Browse, HTTP downloads</span>
              <span>Writes</span><span>No upload, delete, rename, settings, or firmware operations</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <main>
    <section class="connection-panel">
      <div class="section-head">Connection</div>
      <div class="section-body stack">
        <div class="actions">
          <button class="primary" id="discoverBtn">Discover</button>
          <button id="browseBtn">Browse</button>
        </div>
        <label>Manual camera IP
          <input id="ipInput" type="text" placeholder="192.168.5.19">
        </label>
        <div id="cameraList" class="camera-list"></div>
        <div id="status" class="status">Put the camera in AllShare Play / Samsung Link mode on the same Wi-Fi, then click discover.</div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <span>Media</span>
        <span id="count" class="muted tiny">0 files</span>
      </div>
      <div class="section-body stack">
        <div class="toolbar">
          <div class="media-tools">
            <div class="row">
              <button id="selectAllBtn">Select all</button>
              <button id="selectNoneBtn">Select none</button>
            </div>
            <div id="selectedStats" class="muted tiny">0 selected</div>
          </div>
          <div></div>
          <button class="primary" id="downloadBtn">Download selected</button>
        </div>
        <div class="media-control-bar">
          <label>Filter
            <input id="filterInput" type="text" placeholder="SAM_1934 / video / jpg">
          </label>
          <label>Sort
            <select id="sortSelect">
              <option value="date-desc">Newest</option>
              <option value="date-asc">Oldest</option>
              <option value="name-asc">Name A-Z</option>
              <option value="name-desc">Name Z-A</option>
              <option value="size-desc">Size high</option>
              <option value="size-asc">Size low</option>
              <option value="type-asc">Type</option>
            </select>
          </label>
          <div class="view-switch" aria-label="View">
            <button class="view-btn active" data-view="grid">Grid</button>
            <button class="view-btn" data-view="compact">Compact</button>
            <button class="view-btn" data-view="large">Large</button>
            <button class="view-btn" data-view="list">List</button>
          </div>
        </div>
        <div class="media-wrap">
          <div id="mediaBody" class="media-grid"></div>
        </div>
        <div class="stack">
          <progress id="progress" value="0" max="1"></progress>
          <div class="progress-group" aria-hidden="true">
            <div class="progress-row">
              <span>File</span>
              <div class="progress-shell"><div id="fileProgressFill" class="progress-fill"></div></div>
              <span id="fileProgressText">Idle</span>
            </div>
            <div class="progress-row">
              <span>Total</span>
              <div class="progress-shell"><div id="totalProgressFill" class="progress-fill"></div></div>
              <span id="totalProgressText">Idle</span>
            </div>
          </div>
          <button class="folder-link" id="folderLink" title="Open download folder">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 7h6l2 2h10v10H3z"></path>
              <path d="M3 7V5h7l2 2"></path>
            </svg>
            <span id="folderText"></span>
          </button>
          <div id="jobStatus" class="status">No active transfer.</div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const state = { ip: "", files: [], selected: new Set(), job: null, poll: null, discovering: false, discoverTimer: null, view: "grid" };
    const defaultDest = "__DEFAULT_DEST__";
    $("destInput").value = localStorage.getItem("downloadFolder") || defaultDest;

    function setTheme(theme) {
      if (![...document.querySelectorAll(".theme-btn")].some(btn => btn.dataset.theme === theme)) {
        theme = "brutal";
      }
      document.body.dataset.theme = theme;
      localStorage.setItem("theme", theme);
      document.querySelectorAll(".theme-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.theme === theme);
      });
    }
    document.querySelectorAll(".theme-btn").forEach(btn => {
      btn.onclick = () => setTheme(btn.dataset.theme);
    });
    setTheme(localStorage.getItem("theme") || "brutal");
    function setSettingsOpen(open) {
      $("settingsLayer").classList.toggle("open", open);
      $("settingsLayer").setAttribute("aria-hidden", open ? "false" : "true");
    }
    function currentDest() {
      return $("destInput").value.trim() || defaultDest;
    }
    function syncFolderText() {
      $("folderText").textContent = currentDest();
    }
    $("settingsBtn").onclick = () => setSettingsOpen(true);
    $("settingsCloseBtn").onclick = () => setSettingsOpen(false);
    $("settingsLayer").onclick = (event) => {
      if (event.target === $("settingsLayer")) setSettingsOpen(false);
    };
    $("destInput").oninput = () => {
      localStorage.setItem("downloadFolder", currentDest());
      syncFolderText();
    };
    syncFolderText();

    function setStatus(text, cls = "") {
      const el = $("status");
      el.className = "status" + (cls ? " " + cls : "");
      el.textContent = text;
    }
    function setJob(text, cls = "") {
      const el = $("jobStatus");
      el.className = "status" + (cls ? " " + cls : "");
      el.textContent = text;
    }
    function setProgress(done, total, label = "") {
      const pct = total ? Math.round((done / total) * 100) : 0;
      $("progress").max = total || 1;
      $("progress").value = done || 0;
      $("totalProgressFill").style.width = `${Math.max(0, Math.min(100, pct))}%`;
      $("totalProgressText").textContent = label || (total ? `${pct}%` : "Idle");
    }
    function setFileProgress(done, total, label = "") {
      const pct = total ? Math.round((done / total) * 100) : 0;
      $("fileProgressFill").style.width = `${Math.max(0, Math.min(100, pct))}%`;
      $("fileProgressText").textContent = label || (total ? `${pct}%` : "Idle");
    }
    function updateSelectedStats() {
      const indices = selectedIndices();
      const bytes = indices.reduce((sum, index) => sum + (state.files[index]?.size || 0), 0);
      $("selectedStats").textContent = `${indices.length} selected / ${fmtSize(bytes)}`;
    }
    function setDiscovering(on) {
      state.discovering = on;
      $("discoverBtn").textContent = on ? "Stop" : "Discover";
      $("discoverBtn").classList.toggle("primary", !on);
    }
    function stopDiscoveryLoop() {
      if (state.discoverTimer) clearTimeout(state.discoverTimer);
      state.discoverTimer = null;
      setDiscovering(false);
    }
    function setConnected(on) {
      document.body.classList.toggle("connected", on);
    }
    function fmtSize(bytes) {
      if (!bytes) return "0 B";
      const units = ["B", "KB", "MB", "GB"];
      let n = bytes, i = 0;
      while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
      return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    async function api(path, options = {}) {
      const res = await fetch(path, options);
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    }
    function sortableDate(file) {
      const parsed = Date.parse(file.date || "");
      return Number.isFinite(parsed) ? parsed : 0;
    }
    function displayFiles() {
      const filter = $("filterInput").value.trim().toLowerCase();
      const sort = $("sortSelect").value;
      let items = state.files.map((file, index) => ({ file, index }));
      if (filter) {
        items = items.filter(({ file }) => [file.title, file.mime, file.date, file.duration, file.resolution]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(filter));
      }
      const direction = sort.endsWith("desc") ? -1 : 1;
      items.sort((a, b) => {
        if (sort.startsWith("date")) return (sortableDate(a.file) - sortableDate(b.file)) * direction;
        if (sort.startsWith("size")) return ((a.file.size || 0) - (b.file.size || 0)) * direction;
        if (sort.startsWith("type")) return String(a.file.mime || "").localeCompare(String(b.file.mime || ""));
        return String(a.file.title || "").localeCompare(String(b.file.title || "")) * direction;
      });
      return items;
    }
    function renderCameras(cameras) {
      const list = $("cameraList");
      list.innerHTML = "";
      cameras.forEach(cam => {
        const div = document.createElement("div");
        div.className = "camera" + (cam.ip === state.ip ? " active" : "");
        div.innerHTML = `<strong>${cam.name || "Samsung Camera"}</strong>
          <span class="muted tiny">${cam.ip}</span>
          <span class="muted tiny">${cam.model || ""}</span>`;
        div.onclick = () => {
          state.ip = cam.ip;
          $("ipInput").value = cam.ip;
          renderCameras(cameras);
        };
        list.appendChild(div);
      });
    }
    function renderMedia() {
      const body = $("mediaBody");
      body.innerHTML = "";
      body.className = `media-grid view-${state.view}`;
      const items = displayFiles();
      items.forEach(({ file, index }) => {
        const card = document.createElement("div");
        const checked = state.selected.has(index);
        card.className = "media-card" + (checked ? " selected" : "");
        const thumb = file.thumbnail_url
          ? `<img loading="lazy" src="${escapeHtml(file.thumbnail_url)}" alt="">`
          : `<span class="placeholder">${file.mime && file.mime.startsWith("video/") ? "VIDEO" : "IMAGE"}</span>`;
        card.innerHTML = `<input type="checkbox" data-index="${index}" ${checked ? "checked" : ""}>
          <div class="thumb">${thumb}</div>
          <div class="card-meta">
            <div class="card-name" title="${escapeHtml(file.title)}">${escapeHtml(file.title)}</div>
            <div class="card-sub">${fmtSize(file.size)} ${escapeHtml(file.mime || "")}</div>
            <div class="card-extra">${escapeHtml([file.date, file.duration, file.resolution].filter(Boolean).join(" / "))}</div>
          </div>`;
        const checkbox = card.querySelector("input");
        checkbox.onchange = () => {
          if (checkbox.checked) state.selected.add(index);
          else state.selected.delete(index);
          card.classList.toggle("selected", checkbox.checked);
          updateSelectedStats();
        };
        card.onclick = (event) => {
          if (event.target !== checkbox) {
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event("change"));
          }
        };
        body.appendChild(card);
      });
      $("count").textContent = `${items.length}/${state.files.length} file${state.files.length === 1 ? "" : "s"}`;
      updateSelectedStats();
    }
    function selectedIndices() {
      return [...state.selected].sort((a, b) => a - b);
    }
    async function discoverOnce(showTrying = true) {
      try {
        if (showTrying) setStatus("Discovering... approve the camera pairing prompt if it appears.");
        const data = await api("/api/discover");
        renderCameras(data.cameras);
        if (data.cameras[0]) {
          state.ip = data.cameras[0].ip;
          $("ipInput").value = state.ip;
          setConnected(true);
          setStatus(`Connected to ${data.cameras[0].name || "Samsung Camera"} at ${state.ip}!`, "ok");
          return true;
        }
        setStatus("Still searching. Leave the camera in AllShare Play / Samsung Link and accept pairing.", "warn");
        return false;
      } catch (err) {
        setStatus(err.message, "bad");
        return false;
      }
    }
    async function discoverLoop() {
      if (!state.discovering) return;
      const found = await discoverOnce(false);
      if (found) {
        stopDiscoveryLoop();
        return;
      }
      if (state.discovering) state.discoverTimer = setTimeout(discoverLoop, 1800);
    }
    $("discoverBtn").onclick = async () => {
      if (state.discovering) {
        stopDiscoveryLoop();
        setStatus("Discovery stopped.", "warn");
        return;
      }
      setDiscovering(true);
      const found = await discoverOnce(true);
      if (found) {
        stopDiscoveryLoop();
      } else if (state.discovering) {
        state.discoverTimer = setTimeout(discoverLoop, 1800);
      }
    };
    $("browseBtn").onclick = async () => {
      try {
        const ip = $("ipInput").value.trim() || state.ip;
        if (!ip) throw new Error("Enter a camera IP or run Discover first.");
        state.ip = ip;
        setStatus(`Browsing ${ip}...`);
        const data = await api(`/api/browse?ip=${encodeURIComponent(ip)}`);
        state.files = data.files;
        state.selected = new Set(state.files.map((_, index) => index));
        renderMedia();
        setConnected(true);
        setStatus(`Loaded ${data.files.length} files from ${data.camera.name}.`, "ok");
      } catch (err) {
        setStatus(err.message, "bad");
      }
    };
    $("filterInput").oninput = renderMedia;
    $("sortSelect").onchange = renderMedia;
    document.querySelectorAll(".view-btn").forEach(btn => {
      btn.onclick = () => {
        state.view = btn.dataset.view;
        document.querySelectorAll(".view-btn").forEach(item => item.classList.toggle("active", item === btn));
        renderMedia();
      };
    });
    $("selectAllBtn").onclick = () => {
      displayFiles().forEach(({ index }) => state.selected.add(index));
      renderMedia();
    };
    $("selectNoneBtn").onclick = () => {
      displayFiles().forEach(({ index }) => state.selected.delete(index));
      renderMedia();
    };
    $("downloadBtn").onclick = async () => {
      try {
        const ip = $("ipInput").value.trim() || state.ip;
        const indices = selectedIndices();
        if (!ip) throw new Error("Enter a camera IP or run Discover first.");
        if (!indices.length) throw new Error("Select at least one file.");
        const data = await api("/api/download", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ip, indices, dest: currentDest(), new_only: true})
        });
        state.job = data.job_id;
        setProgress(0, indices.length, "0%");
        setFileProgress(0, 0, "Idle");
        setJob("Starting transfer...");
        if (state.poll) clearInterval(state.poll);
        state.poll = setInterval(pollJob, 1000);
        pollJob();
      } catch (err) {
        setJob(err.message, "bad");
      }
    };
    async function pollJob() {
      if (!state.job) return;
      try {
        const job = await api(`/api/jobs/${state.job}`);
        setProgress(job.done || 0, job.total || 0, job.total ? `${job.done || 0}/${job.total || 0}` : job.status);
        setFileProgress(job.current_done || 0, job.current_total || 0, job.current_total ? `${job.current_pct || 0}%` : "Idle");
        setJob(`${job.status}: ${job.message || ""}\n${job.done || 0}/${job.total || 0} complete`, job.status === "failed" ? "bad" : job.status === "done" ? "ok" : "");
        if (job.status === "done" || job.status === "failed") {
          clearInterval(state.poll);
          state.poll = null;
        }
      } catch (err) {
        setJob(err.message, "bad");
        clearInterval(state.poll);
      }
    }
    $("folderLink").onclick = async () => {
      try {
        await api("/api/open-folder", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({path: currentDest()})
        });
        setJob(`Opened ${currentDest()}.`, "ok");
      } catch (err) {
        setJob(err.message, "bad");
      }
    };
  </script>
</body>
</html>
"""
INDEX_HTML = (
    INDEX_HTML
    .replace("__DEFAULT_DEST__", DEFAULT_DEST.replace("\\", "\\\\"))
    .replace("__APP_NAME__", APP_NAME)
    .replace("__APP_VERSION__", APP_VERSION)
    .replace("__APP_TAGLINE__", APP_TAGLINE)
)


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def camera_to_json(camera: camera_client.Camera) -> dict[str, Any]:
    return {
        "ip": camera.device.ip,
        "name": camera.friendly_name,
        "manufacturer": camera.manufacturer,
        "model": " ".join(part for part in [camera.model_name, camera.model_number] if part),
        "control_url": camera.content_directory_url,
    }


def media_to_json(media: camera_client.MediaFile) -> dict[str, Any]:
    return asdict(media)


def find_cameras() -> list[camera_client.Camera]:
    cameras = []
    seen = set()
    for device in camera_client.discover(timeout=4):
        camera = camera_client.camera_from_description(device)
        if camera and camera.device.ip not in seen:
            cameras.append(camera)
            seen.add(camera.device.ip)
    return cameras


def resolve_camera(ip: str) -> camera_client.Camera:
    camera = camera_client.camera_from_ip(ip)
    if not camera:
        raise RuntimeError(f"No Samsung camera service found at {ip}")
    return camera


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform.startswith("win"):
        subprocess.Popen(["explorer", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def download_one(media: camera_client.MediaFile, dest: Path, progress: Any | None = None) -> Path:
    filename = camera_client.safe_filename(media.title, media.mime, media.url)
    target = dest / filename
    if target.exists() and (not media.size or target.stat().st_size == media.size):
        if progress:
            progress(media.size or target.stat().st_size, media.size or target.stat().st_size)
        return target
    if target.exists():
        target = camera_client.unique_path(target)

    tmp = target.with_suffix(target.suffix + ".part")
    req = urllib.request.Request(media.url, headers={"User-Agent": "SamsungWifiWeb/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response, open(tmp, "wb") as out:
        total = int(response.headers.get("Content-Length") or media.size or 0)
        done = 0
        if progress:
            progress(done, total)
        while True:
            chunk = response.read(1024 * 128)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    os.replace(tmp, target)
    return target


def run_download_job(job_id: str, files: list[camera_client.MediaFile], dest: Path) -> None:
    with LOCK:
        JOBS[job_id].update({
            "status": "running",
            "total": len(files),
            "done": 0,
            "message": "Preparing destination",
            "current_file": "",
            "current_done": 0,
            "current_total": 0,
            "current_pct": 0,
        })
    dest.mkdir(parents=True, exist_ok=True)
    try:
        for index, media in enumerate(files, 1):
            filename = camera_client.safe_filename(media.title, media.mime, media.url)
            with LOCK:
                JOBS[job_id].update({
                    "message": f"Downloading {filename}",
                    "current_file": filename,
                    "current_done": 0,
                    "current_total": media.size or 0,
                    "current_pct": 0,
                })

            def update_file_progress(done: int, total: int) -> None:
                pct = round((done / total) * 100) if total else 0
                with LOCK:
                    JOBS[job_id].update({
                        "current_done": done,
                        "current_total": total,
                        "current_pct": max(0, min(100, pct)),
                    })

            download_one(media, dest, update_file_progress)
            with LOCK:
                JOBS[job_id]["done"] = index
        with LOCK:
            JOBS[job_id].update({
                "status": "done",
                "message": f"Saved to {dest}",
                "current_done": 0,
                "current_total": 0,
                "current_pct": 0,
            })
    except Exception as error:
        with LOCK:
            JOBS[job_id].update({"status": "failed", "message": str(error)})


class AppHandler(BaseHTTPRequestHandler):
    server_version = "SamsungWifiWeb/0.1"

    def do_HEAD(self) -> None:
        if urllib.parse.urlparse(self.path).path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(INDEX_HTML.encode("utf-8"))))
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path == "/":
                text_response(self, 200, INDEX_HTML, "text/html; charset=utf-8")
            elif path == "/api/discover":
                cameras = [camera_to_json(camera) for camera in find_cameras()]
                json_response(self, 200, {"cameras": cameras})
            elif path == "/api/browse":
                ip = query.get("ip", [""])[0].strip()
                if not ip:
                    raise RuntimeError("Missing ip")
                camera = resolve_camera(ip)
                files = camera_client.browse_camera(camera)
                with LOCK:
                    MEDIA_CACHE[ip] = files
                json_response(self, 200, {"camera": camera_to_json(camera), "files": [media_to_json(file) for file in files]})
            elif path.startswith("/api/jobs/"):
                job_id = path.rsplit("/", 1)[-1]
                with LOCK:
                    job = JOBS.get(job_id)
                    if not job:
                        raise RuntimeError("Unknown job")
                    payload = dict(job)
                json_response(self, 200, payload)
            else:
                json_response(self, 404, {"error": "Not found"})
        except Exception as error:
            json_response(self, 400, {"error": str(error)})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path not in ("/api/download", "/api/open-folder"):
                json_response(self, 404, {"error": "Not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if parsed.path == "/api/open-folder":
                folder = Path(str(payload.get("path") or DEFAULT_DEST)).expanduser()
                open_folder(folder)
                json_response(self, 200, {"ok": True})
                return

            ip = str(payload.get("ip", "")).strip()
            indices = payload.get("indices", [])
            dest = Path(str(payload.get("dest") or DEFAULT_DEST)).expanduser()
            if not ip:
                raise RuntimeError("Missing ip")
            with LOCK:
                cached = MEDIA_CACHE.get(ip)
            if cached is None:
                camera = resolve_camera(ip)
                cached = camera_client.browse_camera(camera)
                with LOCK:
                    MEDIA_CACHE[ip] = cached
            selected = [cached[int(index)] for index in indices if 0 <= int(index) < len(cached)]
            if not selected:
                raise RuntimeError("No valid files selected")
            job_id = uuid.uuid4().hex
            with LOCK:
                JOBS[job_id] = {"job_id": job_id, "status": "queued", "total": len(selected), "done": 0, "message": ""}
            thread = threading.Thread(target=run_download_job, args=(job_id, selected, dest), daemon=True)
            thread.start()
            json_response(self, 200, {"job_id": job_id})
        except Exception as error:
            json_response(self, 400, {"error": str(error)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def open_browser_later(url: str) -> None:
    time.sleep(0.7)
    webbrowser.open(url)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    url = f"http://{HOST}:{PORT}"
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser_later, args=(url,), daemon=True).start()
    print(f"Nexus.cam web app: {url}")
    print("Close this window to stop Nexus.cam.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
