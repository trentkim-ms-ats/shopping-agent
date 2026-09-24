import json
import os
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app import enrichment


@pytest.fixture
def profile_source(tmp_path, monkeypatch):
    source = enrichment.ROOT / "data/seed/profiles.json"
    path = tmp_path / "data/seed/profiles.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(source.read_bytes())
    monkeypatch.setattr(enrichment, "ROOT", tmp_path)
    enrichment._load_profiles.cache_clear()
    yield path
    enrichment._load_profiles.cache_clear()


def test_profiles_reuse_validated_source_and_isolate_mutations(profile_source, monkeypatch):
    load = Mock(wraps=enrichment.load_json)
    monkeypatch.setattr(enrichment, "load_json", load)
    first = enrichment.profiles()
    first["alex"].budget_cents = 1
    first["alex"].preferred_colors.append("Injected")
    del first["sam"]
    second = enrichment.profiles()
    assert second["alex"].budget_cents == 20000
    assert "Injected" not in second["alex"].preferred_colors
    assert second["sam"].budget_cents == 15000
    assert load.call_count == 1


def test_profiles_refresh_after_source_change(profile_source, monkeypatch):
    load = Mock(wraps=enrichment.load_json)
    monkeypatch.setattr(enrichment, "load_json", load)
    first = enrichment.profiles()
    stat = profile_source.stat()
    data = json.loads(profile_source.read_text())
    data[0]["budget_cents"] = 25000
    profile_source.write_text(json.dumps(data))
    os.utime(profile_source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    updated = enrichment.profiles()
    assert first["alex"].budget_cents == 20000
    assert updated["alex"].budget_cents == 25000
    assert enrichment.profiles()["alex"].budget_cents == 25000
    assert load.call_count == 2


@pytest.mark.parametrize("invalid", ["{", '[{"profile_id":"alex"}]'])
def test_invalid_profiles_raise_instead_of_serving_stale_cache(profile_source, invalid):
    enrichment.profiles()
    profile_source.write_text(invalid)
    with pytest.raises((json.JSONDecodeError, ValidationError)):
        enrichment.profiles()


def test_missing_profiles_raise_instead_of_serving_stale_cache(profile_source):
    enrichment.profiles()
    profile_source.unlink()
    with pytest.raises(FileNotFoundError):
        enrichment.profiles()
