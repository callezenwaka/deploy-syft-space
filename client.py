"""Syft Space API client."""

import requests
from typing import Optional


class SyftClient:
    """Client for Syft Space API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def check_connection(self) -> bool:
        """Verify API connection."""
        try:
            r = requests.get(
                f"{self.base_url}/datasets/types/",
                headers=self._headers(),
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    # -- Datasets --

    def list_datasets(self) -> list:
        r = requests.get(
            f"{self.base_url}/datasets/", headers=self._headers(), timeout=30
        )
        r.raise_for_status()
        return r.json()

    def get_dataset(self, name: str) -> Optional[dict]:
        r = requests.get(
            f"{self.base_url}/datasets/{name}", headers=self._headers(), timeout=10
        )
        if r.status_code == 200:
            return r.json()
        return None

    def create_dataset(self, payload: dict) -> tuple[bool, dict | str]:
        r = requests.post(
            f"{self.base_url}/datasets/",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        if r.status_code == 201:
            return True, r.json()
        elif r.status_code == 409 or "already exists" in r.text.lower():
            existing = self.get_dataset(payload["name"])
            if existing:
                return True, existing
            return False, "Dataset exists but couldn't fetch"
        return False, f"{r.status_code}: {r.text[:200]}"

    def delete_dataset(self, name: str) -> tuple[bool, str]:
        r = requests.delete(
            f"{self.base_url}/datasets/{name}", headers=self._headers(), timeout=30
        )
        if r.status_code in [200, 204]:
            return True, "Deleted"
        elif r.status_code == 404:
            return True, "Not found"
        return False, f"{r.status_code}: {r.text[:200]}"

    # -- Endpoints --

    def list_endpoints(self) -> list:
        r = requests.get(
            f"{self.base_url}/endpoints/", headers=self._headers(), timeout=30
        )
        r.raise_for_status()
        return r.json()

    def get_endpoint(self, slug: str) -> Optional[dict]:
        r = requests.get(
            f"{self.base_url}/endpoints/{slug}", headers=self._headers(), timeout=10
        )
        if r.status_code == 200:
            return r.json()
        return None

    def create_endpoint(self, payload: dict) -> tuple[bool, dict | str]:
        r = requests.post(
            f"{self.base_url}/endpoints/",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        if r.status_code == 201:
            return True, r.json()
        elif r.status_code == 409 or "already exists" in r.text.lower():
            return True, {"slug": payload["slug"], "exists": True}
        return False, f"{r.status_code}: {r.text[:200]}"

    def update_endpoint(self, slug: str, payload: dict) -> tuple[bool, str]:
        r = requests.patch(
            f"{self.base_url}/endpoints/{slug}",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        if r.status_code == 200:
            return True, "Updated"
        return False, f"{r.status_code}: {r.text[:200]}"

    def delete_endpoint(self, slug: str) -> tuple[bool, str]:
        r = requests.delete(
            f"{self.base_url}/endpoints/{slug}", headers=self._headers(), timeout=30
        )
        if r.status_code in [200, 204]:
            return True, "Deleted"
        elif r.status_code == 404:
            return True, "Not found"
        return False, f"{r.status_code}: {r.text[:200]}"

    def publish_endpoint(self, slug: str) -> tuple[bool, str]:
        r = requests.post(
            f"{self.base_url}/endpoints/{slug}/publish",
            headers=self._headers(),
            json={"publish_to_all_marketplaces": True},
            timeout=30,
        )
        if r.status_code in [200, 201]:
            return True, "Published"
        return False, f"{r.status_code}: {r.text[:200]}"
