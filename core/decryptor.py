"""
Decryptor and encryptor helpers using the XOR + zlib method used by community scripts.

This module provides several entrypoints. Some older modules expect a function
named `find_key_for_encrypted_bytes`; that is implemented as a thin wrapper
around `find_crypto_key_for_file`/`find_key_for_encrypted_bytes`.

Functions:
- decrypt_bytes(data: bytes, key: int) -> bytes
- try_decrypt_with_key(data: bytes, key: int) -> bytes
- encrypt_bytes(plaintext: bytes, key: int) -> bytes
- find_key_for_encrypted_bytes(data: bytes, start_key: int = 0) -> int
- find_crypto_key_for_file(path: Path) -> int
- get_crypto_key_from_file(folder: Path) -> Optional[int]
"""
from typing import Optional
from pathlib import Path
import zlib

def _xor_transform(buf: bytearray, key: int):
    # same algorithm used by community scripts
    for i in range(len(buf)):
        v = i + key + 0x23D
        v *= key
        v ^= i % 7
        buf[i] ^= v & 0xFF

def decrypt_bytes(data: bytes, key: int) -> bytes:
    """
    Apply XOR transform with key then zlib.decompress. Raises zlib.error on failure.
    """
    buf = bytearray(data)
    _xor_transform(buf, key)
    return zlib.decompress(buf)

def try_decrypt_with_key(data: bytes, key: int) -> bytes:
    """
    Helper that calls decrypt_bytes and returns decompressed bytes or raises.
    """
    return decrypt_bytes(data, key)

def encrypt_bytes(plaintext: bytes, key: int) -> bytes:
    """
    Compress then XOR-encrypt (inverse of decrypt_bytes).
    """
    comp = zlib.compress(plaintext)
    buf = bytearray(comp)
    _xor_transform(buf, key)
    return bytes(buf)

def find_key_for_encrypted_bytes(data: bytes, start_key: int = 0) -> int:
    """
    Brute-force search for a crypto key given raw encrypted bytes.
    Returns the first integer key that produces valid zlib-decompressable output.
    WARNING: can be slow depending on key value.
    """
    key = start_key
    # loop until we find a key; leave it infinite to match community tools behaviour
    while True:
        try:
            # If this doesn't raise, we found a valid key
            _ = decrypt_bytes(data, key)
            return key
        except zlib.error:
            key += 1
            continue
        except Exception:
            # Some other error (rare); continue searching
            key += 1
            continue

def find_crypto_key_for_file(path: Path, start_key: int = 0) -> int:
    """
    Read file bytes and brute-force a key. Writes !CryptoKey.txt into same folder
    (hex format) and returns the discovered key.
    """
    data = path.read_bytes()
    key = find_key_for_encrypted_bytes(data, start_key=start_key)
    try:
        ckfile = path.parent / "!CryptoKey.txt"
        ckfile.write_text(hex(key))
    except Exception:
        # best-effort; ignore write errors
        pass
    return key

def get_crypto_key_from_file(folder: Path) -> Optional[int]:
    """
    Read !CryptoKey.txt if present in folder, return int or None.
    """
    ck = Path(folder) / "!CryptoKey.txt"
    if ck.exists():
        try:
            return int(ck.read_text().strip(), 16)
        except Exception:
            return None
    return None
