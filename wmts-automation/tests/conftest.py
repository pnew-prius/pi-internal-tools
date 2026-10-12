import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GEOSERVER_PASS", "test-only")

import add_cog as add_cog_mod  # noqa: E402
import gwc as gwc_mod  # noqa: E402
import safety  # noqa: E402
from fake_gs import COGS, FakeGS  # noqa: E402


@pytest.fixture
def fake(monkeypatch):
    f = FakeGS(COGS, prod_workspaces=("COPE-S26", "WW-FULLSYS-26"))
    for mod in (add_cog_mod, gwc_mod, safety):
        monkeypatch.setattr(mod, "call", f.call)
    monkeypatch.setattr(add_cog_mod.time, "sleep", lambda *_: None)
    safety._cache.update(at=0.0, names=set())
    return f
