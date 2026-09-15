"""Windows current-user DPAPI storage; never included in exported projects."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile

FIELDS = ('base', 'model', 'key', 'tts_base', 'tts_model', 'tts_key', 'fish_key', 'fish_model')

def settings_path():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'SRT-Voice-Studio' / 'settings.dpapi'

def protect(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError('Windows 密钥加密/解密失败 / Windows credential encryption or decryption failed')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(ctypes.cast(output.data, ctypes.c_void_p))

def load_settings(path=None):
    path = Path(path) if path else settings_path()
    if not path.exists(): return {}
    data = json.loads(protect(path.read_bytes(), decrypt=True).decode('utf-8'))
    if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
        raise ValueError('本地设置格式错误 / Invalid local settings')
    return {key: data[key] for key in FIELDS if key in data}

def save_settings(data, path=None):
    path = Path(path) if path else settings_path()
    encrypted = protect(json.dumps({key: data.get(key, '') for key in FIELDS}).encode('utf-8'))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encrypted)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists(): temporary.unlink()

def clear_settings(path=None):
    path = Path(path) if path else settings_path()
    path.unlink(missing_ok=True)
