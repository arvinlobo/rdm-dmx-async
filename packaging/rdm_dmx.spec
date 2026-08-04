# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for a single-file Windows executable bundling the FastAPI
backend and the built React frontend (frontend/dist).

Build steps (from the repo root):
    cd frontend && npm install && npm run build && cd ..
    uv sync --extra exe
    uv run pyinstaller packaging/rdm_dmx.spec

Output: dist/rdm-dmx.exe (repo-root dist/ - distinct from frontend/dist).
Double-clicking the exe starts the server on http://127.0.0.1:8000 and
opens it in the default browser.
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")

datas = []
if os.path.isdir(FRONTEND_DIST):
    datas.append((FRONTEND_DIST, "frontend/dist"))

a = Analysis(
    [os.path.join(ROOT, "packaging", "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "uvicorn.logging",
        "serial.tools.list_ports_windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="rdm-dmx",
    console=True,
)
