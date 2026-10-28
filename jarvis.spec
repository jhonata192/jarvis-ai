# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

BASE_DIR = Path(SPECPATH).resolve()

datas = [
    (str(BASE_DIR / "jarvis" / "assets" / "sounds"), "jarvis/assets/sounds"),
    (str(BASE_DIR / "data" / "learnings"), "data/learnings"),
]
datas += collect_data_files("faster_whisper")
datas += collect_data_files("chromadb")
datas += collect_data_files("piper")
datas += collect_data_files("tokenizers")

binaries = []
binaries += collect_dynamic_libs("llama_cpp")
binaries += collect_dynamic_libs("ctranslate2")
binaries += collect_dynamic_libs("piper")
binaries += collect_dynamic_libs("onnxruntime")

# Coleta todos os submódulos do ChromaDB com tratamento de erro
chromadb_submodules = [m for m in collect_submodules("chromadb") if "fastapi" not in m]

hidden_imports = [
    "llama_cpp",
    "faster_whisper",
    "chromadb",
    "chromadb.telemetry.product.posthog",
    "chromadb.telemetry.opentelemetry",
    "chromadb.utils.embedding_functions",
    "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
    "onnxruntime",
    "tokenizers",
    "tqdm",
    "piper",
    "piper.voice",
    "piper.config",
    "edge_tts",
    "pygame",
    "pynput",
    "keyboard",
    "speech_recognition",
    "pycaw",
    "comtypes",
    "psutil"
] + chromadb_submodules

# Verifica se existe arquivo de versão gerado pelo build.bat
version_file = str(BASE_DIR / "version_info.txt") if os.path.exists(BASE_DIR / "version_info.txt") else None

a = Analysis(
    [str(BASE_DIR / "jarvis" / "background_runner.py")],
    pathex=[str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
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
