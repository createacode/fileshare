# -*- mode: python ; coding: utf-8 -*-

import os

version_file = 'version.txt'
if not os.path.exists(version_file):
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write("""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 0, 1, 0),
    prodvers=(2, 0, 1, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(u'040904B0', [
        StringStruct(u'CompanyName', u'XAF'),
        StringStruct(u'FileDescription', u'局域网文件快速传输工具'),
        StringStruct(u'FileVersion', u'2.0.1'),
        StringStruct(u'InternalName', u'FileTransferTool'),
        StringStruct(u'LegalCopyright', u'Copyright © 2026 XAF'),
        StringStruct(u'OriginalFilename', u'FileTransferTool.exe'),
        StringStruct(u'ProductName', u'局域网文件快速传输工具'),
        StringStruct(u'ProductVersion', u'2.0.1')
      ])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)""")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('client', 'client')],
    hiddenimports=[
        'aiohttp', 'qrcode', 'aiofiles', 'PIL',
        'socket', 'asyncio', 'webbrowser', 'platform',
        'logging', 'zipfile', 'json', 'base64',
        'hashlib', 'secrets', 'shutil', 'time',
        'datetime', 'pathlib'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FileTransferTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_entitlements=None,
    icon='app.ico',
    version=version_file
)