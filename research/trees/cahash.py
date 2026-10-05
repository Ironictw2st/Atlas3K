import ctypes,os
d=r"C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
os.add_dll_directory(d)
_lib=ctypes.WinDLL(os.path.join(d,'calibs.modder.x64.dll'))
_f=getattr(_lib,'?murmur_hash@CA@@YAIPEBEI@Z'); _f.restype=ctypes.c_uint32; _f.argtypes=[ctypes.c_char_p,ctypes.c_uint32]
def cah(s): b=s.encode(); return _f(b,len(b))
