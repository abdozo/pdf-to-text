from __future__ import annotations

import os
from typing import Protocol


SERVICE = "app.warraq.desktop"


class SecretStore(Protocol):
    def set(self, reference: str, value: str) -> None: ...
    def get(self, reference: str) -> str: ...
    def delete(self, reference: str) -> None: ...


class KeyringSecretStore:
    """Store API credentials in macOS Keychain or the platform equivalent."""

    def __init__(self) -> None:
        import keyring
        self._keyring = keyring

    def set(self, reference: str, value: str) -> None:
        if not value.strip():
            raise ValueError("مفتاح Gemini فارغ")
        self._keyring.set_password(SERVICE, reference, value.strip())

    def get(self, reference: str) -> str:
        value = self._keyring.get_password(SERVICE, reference)
        if not value:
            raise KeyError("تعذر العثور على سر المفتاح في مخزن النظام")
        return value

    def delete(self, reference: str) -> None:
        try:
            self._keyring.delete_password(SERVICE, reference)
        except self._keyring.errors.PasswordDeleteError:
            pass


class MemorySecretStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, reference: str, value: str) -> None:
        self.values[reference] = value

    def get(self, reference: str) -> str:
        return self.values[reference]

    def delete(self, reference: str) -> None:
        self.values.pop(reference, None)


def create_secret_store() -> SecretStore:
    if os.environ.get("WARRAQ_MEMORY_KEYRING") == "1":
        return MemorySecretStore()
    return KeyringSecretStore()

