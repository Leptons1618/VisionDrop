import pytest

from visiondrop import models


def test_registry_has_expected_models():
    assert "gesture_recognizer" in models.MODEL_URLS
    assert "hand_landmarker" in models.MODEL_URLS
    for url in models.MODEL_URLS.values():
        assert url.startswith("https://") and url.endswith(".task")


def test_unknown_model_raises(tmp_path):
    with pytest.raises(KeyError):
        models.ensure_model("does-not-exist", tmp_path)


def test_existing_model_is_returned_without_download(tmp_path):
    path = tmp_path / "gesture_recognizer.task"
    path.write_bytes(b"cached")
    assert models.ensure_model("gesture_recognizer", tmp_path) == path


def test_missing_model_is_downloaded(monkeypatch, tmp_path):
    def fake_urlretrieve(url, filename):
        with open(filename, "wb") as handle:
            handle.write(b"model-bytes")
        return filename, None

    monkeypatch.setattr(models.urllib.request, "urlretrieve", fake_urlretrieve)
    path = models.ensure_model("hand_landmarker", tmp_path)

    assert path.read_bytes() == b"model-bytes"
    assert not path.with_suffix(".task.part").exists()


def test_default_model_dir_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("VISIONDROP_MODEL_DIR", str(tmp_path))
    assert models.default_model_dir() == tmp_path


def test_default_model_dir_falls_back_to_cache(monkeypatch):
    monkeypatch.delenv("VISIONDROP_MODEL_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg-test")
    assert models.default_model_dir() == models.Path("/tmp/xdg-test/visiondrop/models")
