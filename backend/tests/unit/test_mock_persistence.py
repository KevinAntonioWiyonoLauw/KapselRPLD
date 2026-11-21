"""Unit test: mock server file-backed persistence (#18)."""
import importlib
import json
import os
import sys


def test_persistence_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PERSIST_DIR", str(tmp_path))
    # Import a fresh copy of the mock module with persistence enabled.
    sys.modules.pop("mock_main", None)
    spec = importlib.util.spec_from_file_location(
        "mock_main", os.path.join(os.path.dirname(__file__), "..", "..", "..", "mocks", "main.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Write a resource into a bucket and persist it.
    mod._store("openmrs", "Patient")["p1"] = {"resourceType": "Patient", "id": "p1"}
    mod._persist("openmrs", "Patient")
    path = os.path.join(str(tmp_path), "openmrs__Patient.json")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh)["p1"]["id"] == "p1"

    # Simulate a restart: clear in-memory STORE, then _load_all() restores it.
    mod.STORE.clear()
    mod._load_all()
    assert mod.STORE[("openmrs", "Patient")]["p1"]["id"] == "p1"


def test_persistence_off_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_PERSIST_DIR", "")
    spec = importlib.util.spec_from_file_location(
        "mock_main2", os.path.join(os.path.dirname(__file__), "..", "..", "..", "mocks", "main.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._store("openmrs", "Patient")["x"] = {"id": "x"}
    mod._persist("openmrs", "Patient")  # should not raise / write anything
    assert list(tmp_path.iterdir()) == []
