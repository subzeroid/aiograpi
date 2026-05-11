import importlib
import time

import aiograpi.utils as utils


def test_legacy_utils_exports_stay_available():
    assert utils.InstagramIdCodec.decode(utils.InstagramIdCodec.encode(123456789)) == 123456789
    assert utils.dumps({"enabled": True}) == '{"enabled":true}'
    assert utils.json_value({"a": [{"b": 1}]}, "a", 0, "b") == 1
    assert utils.gen_token(8)
    assert utils.gen_password(8)
    assert utils.generate_signature("{}").startswith("signed_body=SIGNATURE.")
    assert utils.generate_jazoest("abc") == "2294"
    assert utils.date_time_original(time.gmtime(0)) == "19700101T000000.000Z"


def test_utils_submodules_are_importable():
    expected = {
        "aiograpi.utils.auth": ["gen_token", "generate_signature", "generate_jazoest"],
        "aiograpi.utils.ids": ["InstagramIdCodec"],
        "aiograpi.utils.serialization": ["InstagrapiJSONEncoder", "dumps", "json_value"],
        "aiograpi.utils.timing": ["date_time_original", "random_delay"],
        "aiograpi.utils.validation": ["vassert"],
        "aiograpi.utils.video": ["analyze_video_for_upload", "read_video_metadata"],
    }
    for module_name, names in expected.items():
        module = importlib.import_module(module_name)
        for name in names:
            assert hasattr(module, name), f"{module_name}.{name} is missing"
