"""运行时数据目录：可写时用程序旁目录，否则回退用户目录。"""

from __future__ import annotations

import os

import pytest

from skyblock_bazaar import paths


def test_prefers_writable_base_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BASE_DIR", tmp_path)
    assert paths.default_data_dir() == tmp_path / "bazaar_config"


@pytest.mark.skipif(os.name == "nt", reason="POSIX 权限模型")
def test_falls_back_to_xdg_when_base_is_read_only(tmp_path, monkeypatch):
    base = tmp_path / "opt"
    base.mkdir()
    base.chmod(0o555)
    try:
        monkeypatch.setattr(paths, "BASE_DIR", base)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert paths.default_data_dir() == tmp_path / "xdg" / "skyblock-bazaar" / "bazaar_config"
    finally:
        base.chmod(0o755)
