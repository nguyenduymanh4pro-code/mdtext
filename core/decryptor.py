"""
Decryptor and encryptor helpers using the XOR + zlib method used by community scripts.

Functions:
- try_get_crypto_key(filename) -> int
- decrypt_bytes(data: bytes, key: int) -> bytes (decompressed) or raises
- encrypt_bytes(plaintext: bytes, key: int) -> bytes (encrypted compressed)
"""
from typing import Optional
import zlib
from pathlib import Path

def _xor_transform(buf: bytearray, key: int):
    for i in range(len(buf)):
        v = i + key + 0x23D
        v *= key
        v ^= i % 7
        buf[i] ^= v & 0xFF

def decrypt_bytes(data: bytes, key: int) -> bytes:
    buf = bytearray(data)
    _xor_transform(buf, key)
    return zlib.decompress(buf)

def try_decrypt_with_key(data: bytes, key: int) -> bytes:
    # return decompressed bytes or raise zlib.error
    return decrypt_bytes(data, key)

def find_crypto_key_for_file(path: Path) -> Optional[int]:
    """
    Brute-force search for crypto key by trying increasing ints until zlib.decompress succeeds.
    Writes !CryptoKey.txt in same folder for convenience.
    """
    data = path.read_bytes()
    key = -1
    while True:
        key += 1
        try:
            decrypt_bytes(data, key)
            # save key
            ckfile = path.parent / "!CryptoKey.txt"
            ckfile.write_text(hex(key))
            return key
        except zlib.error:
            continue
        except Exception:
            # other errors like overflow etc, continue
            continue

def get_crypto_key_from_file(folder: Path) -> Optional[int]:
    ck = folder / "!CryptoKey.txt"
    if ck.exists():
        try:
            return int(ck.read_text(), 16)
        except Exception:
            return None
    return None

def encrypt_bytes(plaintext: bytes, key: int) -> bytes:
    comp = zlib.compress(plaintext)
    buf = bytearray(comp)
    _xor_transform(buf, key)
    return bytes(buf)