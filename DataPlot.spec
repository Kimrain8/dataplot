# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# 核心：强制收集 mysql 相关的所有动态库、数据和隐藏模块，保留 C 扩展
datas, binaries, hiddenimports = collect_all('mysql')
hiddenimports += collect_submodules('mysql.connector')

# 如果你需要把外部的 utils 目录打包进去（假设它在项目根目录下）
# 如果 utils 在外层目录，请将 'utils' 替换为 'D:/pyprj/cv2/utils'
utils_data = [('utils', 'utils')] if os.path.exists('utils') else []

# 收集 templates 模板文件夹
templates_data = [('templates', 'templates')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,           # 注入 mysql 收集到的底层 DLL
    datas=datas + utils_data + templates_data,  # 注入 mysql 数据 + 模板 + utils
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