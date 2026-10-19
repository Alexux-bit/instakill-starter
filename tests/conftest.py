import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from scripts.seed_db import seed


class FakeEncoder:
    """Deterministic bag-of-tokens encoder so tests never load MiniLM."""

    dim = 32

    def encode(self, texts):
        matrix = np.zeros((len(texts), self.dim), dtype=np.float64)
        for row, text in enumerate(texts):
            for token in text.lower().split():
                matrix[row, sum(ord(ch) for ch in token) % self.dim] += 1.0
        return matrix


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("INSTAKILL_DB_PATH", str(tmp_path / "test.db"))
    seed()
    application = create_app(encoder=FakeEncoder())
    with TestClient(application) as test_client:
        yield test_client
