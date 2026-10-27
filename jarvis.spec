# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

BASE_DIR = Path(r"c:\Users\fjhon\jarvis_ai")

# Coleta arquivos de dados e binários das bibliotecas essenciais
datas = [
    (str(BASE_DIR / "jarvis" / "assets" / "sounds"), "jarvis/assets/sounds"),
    (str(BASE_DIR / "data" / "learnings"), "data/learnings"),
]
datas += collect_data_files("faster_whisper")
datas += collect_data_files("chromadb")

binaries = []
binaries += collect_dynamic_libs("llama_cpp")
binaries += collect_dynamic_libs("ctranslate2")

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
    console=False,  # Sem janela de console (totalmente silencioso em segundo plano)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
