# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

datas, binaries, hiddenimports = collect_all('mysql')
hiddenimports += collect_submodules('mysql.connector', on_error='ignore')

# PySide6：只收集必要的数据，不 collect_submodules 全部
datas += collect_data_files('PySide6')
# 手动补充确实用到的 PySide6 模块，而非全部
hiddenimports += [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtSvg',
    'PySide6.QtTest',
    'shiboken6',
]

# pyqtgraph：只收集子模块，跳过两个已不存在的模板
hiddenimports += collect_submodules('pyqtgraph', on_error='ignore')

utils_data = [('utils', 'utils')] if os.path.exists('utils') else []
templates_data = [('templates', 'templates')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas + utils_data + templates_data,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pyarrow', 'IPython', 'jupyter'],
    noarchive=False,
)

# 过滤掉 OpenGL 旧版 vc9 DLL（消除 MSVCR90.dll 警告，减小体积）
a.binaries = [b for b in a.binaries if 'vc9.dll' not in b[0].lower()]

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
    console=False,               # 设置为 True 可以在打包后看到控制台 print
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None                   # 如果你有 ico 文件，可以在这里写路径，如 'icon.ico'
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