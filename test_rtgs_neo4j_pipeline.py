import rtgs_neo4j_pipeline as neo


class _FakeResult:
    def single(self):
        return {"status": "ok"}


class _FakeSession:
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, q, **kwargs):
        self.queries.append((q, kwargs))
        return _FakeResult()


class _FakeDriver:
    def verify_connectivity(self):
        return None

    def session(self, database=None):
        return _FakeSession()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_wait_and_validate_connection(monkeypatch):
    monkeypatch.setattr(neo, "_driver", lambda uri, username, password: _FakeDriver())
    out = neo.wait_and_validate_connection("neo4j+s://x", "u", "p", "neo4j", wait_seconds=0)
    assert out["status"] == "ok"
    assert out["database"] == "neo4j"
