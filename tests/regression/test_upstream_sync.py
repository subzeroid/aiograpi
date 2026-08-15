from pathlib import Path

import aiograpi


def test_upstream_instagrapi_baseline_is_recorded():
    assert aiograpi.__upstream_instagrapi_version__ == "2.18.15"


def test_upstream_sync_doc_matches_recorded_baseline():
    docs = Path("docs/upstream-sync.md").read_text()

    assert f"instagrapi {aiograpi.__upstream_instagrapi_version__}" in docs
