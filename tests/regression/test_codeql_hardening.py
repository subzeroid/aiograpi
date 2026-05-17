import os
from pathlib import Path


def test_clip_tmp_path_helper_creates_reserved_unique_paths():
    from aiograpi.mixins.clip import _make_tmp_path

    first = _make_tmp_path(".m4a")
    second = _make_tmp_path(".m4a")
    try:
        assert first != second
        assert first.endswith(".m4a")
        assert second.endswith(".m4a")
        assert os.path.exists(first)
        assert os.path.exists(second)
    finally:
        for path in (first, second):
            if os.path.exists(path):
                os.remove(path)


def test_clip_mixin_does_not_use_insecure_mktemp():
    source = Path("aiograpi/mixins/clip.py").read_text()

    assert "tempfile.mktemp" not in source


def test_challenge_ajax_seed_is_not_named_like_a_password():
    source = Path("aiograpi/mixins/challenge.py").read_text()

    assert 'enc_password = "#PWD_INSTAGRAM_BROWSER' not in source
    assert "hashlib.sha256(enc_password.encode())" not in source
    assert "ajax_seed" in source
