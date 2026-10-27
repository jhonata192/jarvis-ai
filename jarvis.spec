# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

BASE_DIR = Path(SPECPATH).resolve()

datas = [
    (str(BASE_DIR / "jarvis" / "assets" / "sounds"), "jarvis/assets/sounds"),
    (str(BASE_DIR / "data" / "learnings"), "data/learnings"),
]
datas += collect_data_files("faster_whisper")
datas += collect_data_files("chromadb")

binaries = []
binaries += collect_dynamic_libs("llama_cpp")
binaries += collect_dynamic_libs("ctranslate2")

# Verifica se existe arquivo de versão gerado pelo build.bat
version_file = str(BASE_DIR / "version_info.txt") if os.path.exists(BASE_DIR / "version_info.txt") else None

a = Analysis(
    [str(BASE_DIR / "jarvis" / "background_runner.py")],
    pathex=[str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "llama_cpp",
        "faster_whisper",
        "chromadb",
        "chromadb.api.segment",
        "chromadb.db.impl.sqlite",
        "edge_tts",
        "pygame",
        "pynput",
        "keyboard",
        "speech_recognition",
        "pycaw",
        "comtypes",
        "psutil"
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JarvisAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JarvisAI',
)
