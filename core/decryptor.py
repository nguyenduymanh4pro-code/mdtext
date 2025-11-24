"""
Community XOR+zlib crypto implementation (from _CARD_decrypt and _CARD_encrypt).
Functions:
- xor_transform (in-place)
- decrypt_bytes(data, key) -> decompressed bytes
- encrypt_bytes(plain, key) -> encrypted bytes (zlib compressed + XOR)
- find_key_for_encrypted_bytes(b, start=0, max_trials=1<<16)
"""
import zlib

def xor_transform(arr: bytearray, key: int):
    for i in range(len(arr)):
        v = i + key + 0x23D
        v *= key
        v ^= i % 7
        arr[i] ^= v & 0xFF
    return arr

def decrypt_bytes(data: bytes, key: int) -> bytes:
    arr = bytearray(data)
    xor_transform(arr, key)
    return zlib.decompress(arr)

def encrypt_bytes(plain: bytes, key: int) -> bytes:
    comp = zlib.compress(plain)
    arr = bytearray(comp)
    xor_transform(arr, key)
    return bytes(arr)

def find_key_for_encrypted_bytes(b: bytes, start=0, max_trials=1<<16):
    for k in range(start, start + max_trials):
        try:
            _ = decrypt_bytes(b, k)
            return k
        except zlib.error:
            continue
    raise RuntimeError("crypto key not found in range")