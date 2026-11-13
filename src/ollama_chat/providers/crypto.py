# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
API key encryption - AES-GCM with a locally stored master key. The master key is generated on
first use and stored in a file next to the config file (never committed to git). Encrypted
API keys are stored in the config as hex "iv:cipher16:cipher" (the AES-GCM 12-byte nonce, then
the ciphertext with its first 16 bytes split off, as in the CRM implementation this follows).
"""

import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# The master key file name, stored next to the config file
KEY_FILENAME = 'ollama-chat.key'

# The mask shown in place of a saved key too short to show a partial mask
_KEY_MASK_SHORT = '••••'


# The master-key-backed API key encryption. One instance per application, constructed with the
# config path - the master key file lives in the same directory as the config file.
class CryptoManager:
    __slots__ = ('key_path',)


    def __init__(self, config_path):
        self.key_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), KEY_FILENAME)


    # The 32-byte AES-256 master key, loading it from the key file or generating and saving a
    # new one. Raises OSError if the key file can't be written.
    def _get_key(self):
        try:
            with open(self.key_path, 'r', encoding='utf-8') as key_fh:
                key = bytes.fromhex(key_fh.read().strip())
            if len(key) == 32:
                return key
        except (OSError, ValueError):
            pass

        # Generate a new master key, writing it owner-readable only where the OS allows it
        key = secrets.token_bytes(32)
        key_fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(key_fd, 'w', encoding='utf-8') as key_fh:
            key_fh.write(key.hex())
        if os.name == 'posix':
            os.chmod(self.key_path, 0o600)
        return key


    # Encrypt an API key, returning the "iv:cipher16:cipher" hex string. An empty key encrypts
    # to an empty string.
    def encrypt_api_key(self, plaintext):
        if not plaintext:
            return ''
        key = self._get_key()
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode('utf-8'), None)
        return f'{nonce.hex()}:{ciphertext[:16].hex()}:{ciphertext[16:].hex()}'


    # Decrypt an API key encrypted with encrypt_api_key. An empty ciphertext decrypts to an
    # empty string; a malformed or undecryptable one (e.g. a different master key) raises
    # ValueError.
    def decrypt_api_key(self, ciphertext):
        if not ciphertext:
            return ''
        key = self._get_key()
        parts = ciphertext.split(':')
        if len(parts) != 3:
            raise ValueError('malformed encrypted API key')
        try:
            nonce = bytes.fromhex(parts[0])
            encrypted = bytes.fromhex(parts[1]) + bytes.fromhex(parts[2])
            return AESGCM(key).decrypt(nonce, encrypted, None).decode('utf-8')
        except ValueError:
            raise ValueError('the encrypted API key could not be decrypted') from None


    # The saved key's display mask - enough to recognize it, never enough to use it. An
    # undecryptable saved key masks as fully hidden rather than failing.
    def key_mask(self, ciphertext):
        try:
            plaintext = self.decrypt_api_key(ciphertext)
        except ValueError:
            return _KEY_MASK_SHORT
        return mask_api_key(plaintext)


# Mask an API key for display - the first 6 and last 4 characters, e.g. "sk-ant-••••3xyz" is
# shown for a key starting "sk-ant-..."
def mask_api_key(plaintext):
    if not plaintext or len(plaintext) <= 10:
        return _KEY_MASK_SHORT
    return f'{plaintext[:6]}••••{plaintext[-4:]}'
