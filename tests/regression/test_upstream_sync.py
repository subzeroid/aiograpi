import aiograpi


def test_upstream_instagrapi_baseline_is_recorded():
    assert aiograpi.__upstream_instagrapi_version__ == "2.17.2"
