# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# 核心：强制收集 mysql 相关的所有动态库、数据和隐藏模块
datas, binaries, hiddenimports = collect_all('mysql')
hiddenimports += collect_submodules('mysql.connector')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,           # 注入收集到的底层 DLL
    datas=datas,                 # 注入收集到的数据文件
    hiddenimports=hiddenimports, # 注入所有隐藏的 Python 模块
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
    [],
    exclude_binaries=True,
    name='DataPlot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DataPlot',
)
