# protects: Only pinned source builds and matching protected cache bytes can reach the native loader.
# fails_when: Unregistered/tampered code is loaded, extraction escapes, build policy changes, or failed rebuilds replace good code.
# why_new: The original official-asset checksum test cannot validate the dedicated local-build trust boundary.
# seam: none
"""Protect the explicit source-build and native-loader trust boundary."""

import hashlib
import importlib
import importlib.resources
import importlib.util
import io
import json
import os
import stat
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture(autouse=True)
def private_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


def build_module():
    assert importlib.util.find_spec("aiograpi.utls_build") is not None, "Explicit source installer is missing"
    return importlib.import_module("aiograpi.utls_build")


def native_module():
    assert importlib.util.find_spec("aiograpi.utls_native") is not None, "Verified native loader is missing"
    return importlib.import_module("aiograpi.utls_native")


def test_native_resources_retain_the_verified_source_pins():
    expected = {
        "LICENSES.txt": "73f3f0ecc099373ba6e3854e3054a41b9378c550c12acbe40ec3074f3be8ddb7",
        "bridge.go": "5ae00bdfb44db83f6076b67d1da2322a64da71fb44052e7b1008d09e213d7cd3",
        "contracts_test.go": "4cf2bc54c9819882bc5d55f1a5b76ad5e355b5cfa1dedd9e352224d2c24aaf74",
        "go.mod": "8784b8ae07fc8caa89d60a409b4f7b7fda224878a93e7818af98dc8f5c8dadde",
        "go.sum": "4050efc8faa7726263bc38965a0070920b44df251e7891d7b0a522a5751de2d4",
        "patches.json": "37c49ad2505de59349240d9fec4d72f772c50e27dbf8152073e35643e4faab76",
        "peer_contracts_test.go": "17cbcfcf82c96552fcb3ae52bfc66e1ee51b7ed96bfe2f7c026a05f818848a31",
    }
    directory = importlib.resources.files("aiograpi").joinpath("native")
    assert directory.is_dir(), "Packaged native source resources are missing"
    actual = {entry.name: hashlib.sha256(entry.read_bytes()).hexdigest() for entry in directory.iterdir()}
    assert actual == expected


def test_native_build_cache_and_deployment_names_are_private_to_aiograpi(tmp_path):
    cached = record_build(b"synthetic-aiograpi-native-code")
    assert cached.is_relative_to(tmp_path / "cache" / "aiograpi" / "utls-native")
    assert not (tmp_path / "cache" / "instagrapi").exists()
    assert native_module().native_library_asset().name.startswith("aiograpi-utls-")


def record_build(data):
    record = getattr(native_module(), "_record_build", None)
    assert callable(record), "Only an explicit source build may register a native checksum"
    return record(data)


@pytest.mark.skipif(os.name == "nt", reason="POSIX umask and cache ownership contract")
def test_new_cache_ancestors_are_private_under_group_writable_umask(tmp_path):
    previous = os.umask(0o002)
    try:
        cached = record_build(b"synthetic-group-umask-build")
    finally:
        os.umask(previous)
    for directory in (
        tmp_path / "cache",
        *(parent for parent in cached.parents if parent.is_relative_to(tmp_path / "cache")),
    ):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert native_module().native_library_asset().sha256 == hashlib.sha256(cached.read_bytes()).hexdigest()


@pytest.mark.skipif(os.name == "nt", reason="POSIX untrusted ancestor contract")
def test_unsafe_cache_is_rejected_before_compilation_or_deployment(monkeypatch, tmp_path):
    module = build_module()
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    cache.chmod(0o770)
    compiler = Mock(side_effect=AssertionError("Unsafe cache reached the compiler"))
    monkeypatch.setattr(module, "_compile_native_library", compiler)
    with pytest.raises(RuntimeError, match="ancestors"):
        module.build_native_library(tmp_path / "installed", rebuild=True)
    compiler.assert_not_called()
    assert stat.S_IMODE(cache.stat().st_mode) == 0o770
    assert not (tmp_path / "installed").exists()


def test_prebuilt_checksum_alone_cannot_authorize_unregistered_native_code(monkeypatch, tmp_path):
    payload = b"synthetic-prebuilt-code"
    path = tmp_path / "unregistered-library"
    path.write_bytes(payload)
    # Reproduce the old public prebuilt-asset approval seam. A source build
    # receipt must now be independently required before calling ctypes.
    monkeypatch.setattr(
        native_module(),
        "native_library_asset",
        lambda: native_module().NativeLibraryAsset(path.name, hashlib.sha256(payload).hexdigest()),
    )
    loader = Mock()
    monkeypatch.setattr(native_module().ctypes, "CDLL", loader)
    with pytest.raises(RuntimeError, match="build"):
        native_module().load_library(path)
    loader.assert_not_called()


def test_registered_build_loads_only_protected_matching_cache_bytes(monkeypatch, tmp_path):
    payload = b"synthetic-locally-built-code"
    cached = record_build(payload)
    supplied = tmp_path / "user-copy"
    supplied.write_bytes(payload)
    library = Mock()
    library.instagrapiNativeABI.return_value = 1
    loader = Mock(return_value=library)
    monkeypatch.setattr(native_module().ctypes, "CDLL", loader)
    assert native_module().load_library(supplied) is library
    loader.assert_called_once_with(str(cached.resolve()))
    library.instagrapiNativeABI.assert_called_once_with()
    assert cached.read_bytes() == payload
    if os.name != "nt":
        assert stat.S_IMODE(cached.stat().st_mode) == 0o600


# Value: protects=unsafe/stale cache material never reaches CDLL;
# fails_when=symlink/ownership/receipt validation is removed;
# why_new=existing tamper is malformed bytes or group mode only; seam=none
@pytest.mark.parametrize(
    "tamper",
    [
        "supplied",
        "cached",
        "receipt",
        "receipt-source",
        "receipt-target",
        "receipt-schema",
        "receipt-digest",
        "receipt-extra-field",
        "cache-symlink",
        "receipt-symlink",
        "blob-symlink",
        *[
            pytest.param(
                name,
                marks=pytest.mark.skipif(os.name == "nt", reason="POSIX owner/mode contract; Windows uses profile ACL"),
            )
            for name in ("blob-mode", "blob-owner", "directory-owner", "writable-ancestor")
        ],
    ],
)
def test_tampered_build_material_is_rejected_before_native_load(monkeypatch, tmp_path, tamper):
    payload = b"synthetic-locally-built-code"
    cached = record_build(payload)
    supplied = tmp_path / "user-copy"
    supplied.write_bytes(payload)
    receipt = cached.parent / "build.json"
    if tamper in {"supplied", "cached", "receipt"}:
        target = {"supplied": supplied, "cached": cached, "receipt": receipt}[tamper]
        target.write_bytes(b"tampered")
    elif tamper.startswith("receipt-") and tamper != "receipt-symlink":
        changes = {
            "receipt-source": {"source": "0" * 64},
            "receipt-target": {"target": "unsupported-target"},
            "receipt-schema": {"schema": 2},
            "receipt-digest": {"sha256": "g" * 64},
            "receipt-extra-field": {"untrusted_approval": True},
        }
        receipt.write_text(json.dumps(json.loads(receipt.read_text()) | changes[tamper]))
    elif tamper.endswith("-symlink"):
        target = {"cache-symlink": cached.parent, "receipt-symlink": receipt, "blob-symlink": cached}[tamper]
        relocated = target.with_name(target.name + "-actual")
        target.rename(relocated)
        target.symlink_to(relocated, target_is_directory=tamper == "cache-symlink")
    elif tamper == "blob-mode":
        cached.chmod(0o640)
    elif tamper == "writable-ancestor":
        (tmp_path / "cache").chmod(0o777)
    else:
        target = cached if tamper == "blob-owner" else cached.parent
        operation = "lstat" if tamper == "blob-owner" else "stat"
        original = getattr(Path, operation)

        def foreign_owner(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == target:
                fields = list(info)
                fields[4] = os.getuid() + 1
                return os.stat_result(fields)
            return info

        monkeypatch.setattr(Path, operation, foreign_owner)
    loader = Mock()
    monkeypatch.setattr(native_module().ctypes, "CDLL", loader)
    with pytest.raises(RuntimeError):
        native_module().load_library(supplied)
    loader.assert_not_called()


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode contract; Windows uses the user profile ACL")
def test_group_writable_native_cache_is_rejected_before_load(monkeypatch):
    cached = record_build(b"synthetic-code")
    cached.parent.chmod(0o770)
    loader = Mock()
    monkeypatch.setattr(native_module().ctypes, "CDLL", loader)
    with pytest.raises(RuntimeError, match="private"):
        native_module().load_library(cached)
    loader.assert_not_called()


def test_wrong_native_abi_is_rejected_before_request_operations(monkeypatch):
    cached = record_build(b"synthetic-code")
    library = Mock()
    library.instagrapiNativeABI.return_value = 0
    monkeypatch.setattr(native_module().ctypes, "CDLL", Mock(return_value=library))
    with pytest.raises(RuntimeError, match="ABI"):
        native_module().load_library(cached)
    library.request.assert_not_called()


def downloaded(payload):
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_bytes.return_value = [payload]
    return response


def test_bad_source_checksum_is_rejected_before_extraction(monkeypatch, tmp_path):
    module = build_module()
    download = Mock(return_value=downloaded(b"untrusted-archive"))
    monkeypatch.setattr(module.httpx, "stream", download)
    source = {"name": "fixture", "version": "v1", "sha256": "0" * 64, "size": 1024}
    with pytest.raises(RuntimeError, match="checksum"):
        module._fetch_source(source, tmp_path / "source")
    assert not (tmp_path / "source").exists()


def test_verified_archive_cannot_extract_outside_destination(monkeypatch, tmp_path):
    module = build_module()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("github.com/bogdanfinn/fixture@v1/../escape", "fixture")
    payload = stream.getvalue()
    source = {"name": "fixture", "version": "v1", "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
    monkeypatch.setattr(module.httpx, "stream", Mock(return_value=downloaded(payload)))
    with pytest.raises(RuntimeError, match="archive"):
        module._fetch_source(source, tmp_path / "source")
    assert not (tmp_path / "escape").exists()


def test_valid_source_archive_is_extracted_after_checksum_verification(monkeypatch, tmp_path):
    module = build_module()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("github.com/bogdanfinn/fixture@v1/source.go", "synthetic-source")
    payload = stream.getvalue()
    source = {"name": "fixture", "version": "v1", "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
    download = Mock(return_value=downloaded(payload))
    monkeypatch.setattr(module.httpx, "stream", download)
    module._fetch_source(source, tmp_path / "source")
    assert (tmp_path / "source" / "source.go").read_text() == "synthetic-source"
    args, kwargs = download.call_args
    assert args == ("GET", "https://proxy.golang.org/github.com/bogdanfinn/fixture/@v/v1.zip")
    assert kwargs["timeout"].connect == 10
    assert kwargs["timeout"].read == 60
    assert kwargs["timeout"].write == 60
    assert kwargs["timeout"].pool == 60


def test_source_download_stops_at_the_pinned_size_before_extraction(monkeypatch, tmp_path):
    module = build_module()
    response = downloaded(b"unused")
    response.iter_bytes.return_value = [b"first", b"excess"]
    monkeypatch.setattr(module.httpx, "stream", Mock(return_value=response))
    source = {"name": "fixture", "version": "v1", "sha256": "0" * 64, "size": 5}
    with pytest.raises(RuntimeError, match="pinned size"):
        module._fetch_source(source, tmp_path / "source")
    response.iter_bytes.assert_called_once_with(65536)
    assert not (tmp_path / "source").exists()


def test_existing_verified_build_is_reused_without_network_or_compiler(monkeypatch, tmp_path):
    module = build_module()
    payload = b"synthetic-built-code"
    record_build(payload)
    network = Mock(side_effect=AssertionError("Unexpected source download"))
    compiler = Mock(side_effect=AssertionError("Unexpected compiler invocation"))
    monkeypatch.setattr(module.httpx, "stream", network)
    monkeypatch.setattr(module.subprocess, "run", compiler)
    path = module.build_native_library(tmp_path / "installed")
    assert path.read_bytes() == payload
    network.assert_not_called()
    compiler.assert_not_called()


def test_missing_go_fails_before_download_or_registration(monkeypatch, tmp_path):
    module = build_module()
    network = Mock(side_effect=AssertionError("Unexpected source download"))
    monkeypatch.setattr(module.httpx, "stream", network)
    monkeypatch.setattr(module.shutil, "which", Mock(return_value=None))
    with pytest.raises(RuntimeError, match="Go"):
        module.build_native_library(tmp_path / "installed")
    network.assert_not_called()
    assert not list((tmp_path / "cache").rglob("build.json"))


@pytest.mark.parametrize("version", ["1.26.9", "1.27.0", "1.27.1"])
def test_vulnerable_go_toolchain_is_rejected_before_source_download(monkeypatch, tmp_path, version):
    module = build_module()
    monkeypatch.setattr(module.shutil, "which", Mock(return_value="/synthetic/go"))
    monkeypatch.setattr(
        module.subprocess,
        "run",
        Mock(return_value=Mock(returncode=0, stdout=f"go version go{version} fixture/fixture", stderr="")),
    )
    network = Mock(side_effect=AssertionError("Unsupported compiler reached source download"))
    monkeypatch.setattr(module.httpx, "stream", network)
    with pytest.raises(RuntimeError, match="Go >= 1.27.2"):
        module.build_native_library(tmp_path / "installed")
    network.assert_not_called()
    assert not list((tmp_path / "cache").rglob("build.json"))


def test_installer_preserves_network_policy_and_omits_account_secrets(monkeypatch, tmp_path):
    module = build_module()
    monkeypatch.setattr(module.shutil, "which", Mock(return_value="/synthetic/go"))
    compiler = Mock(return_value=Mock(returncode=0, stdout="go version go1.27.2 fixture/fixture", stderr=""))
    monkeypatch.setattr(module.subprocess, "run", compiler)
    monkeypatch.setattr(module.httpx, "stream", Mock(return_value=downloaded(b"untrusted-archive")))
    monkeypatch.setenv("HTTPS_PROXY", "http://fixture.invalid:8080")
    monkeypatch.setenv("SSL_CERT_FILE", "/synthetic/ca.pem")
    monkeypatch.setenv("IG_PASSWORD", "synthetic-account-secret")
    monkeypatch.setenv("GOFLAGS", "-overlay=/synthetic/untrusted")
    with pytest.raises(RuntimeError, match="checksum"):
        module.build_native_library(tmp_path / "installed")
    environment = compiler.call_args.kwargs["env"]
    assert environment["HTTPS_PROXY"] == "http://fixture.invalid:8080"
    assert environment["SSL_CERT_FILE"] == "/synthetic/ca.pem"
    assert environment["GOFLAGS"] == "-mod=readonly"
    assert "IG_PASSWORD" not in environment


def test_android_runtime_is_rejected_before_native_build(monkeypatch):
    monkeypatch.setattr(sys, "getandroidapilevel", lambda: 35, raising=False)
    with pytest.raises(RuntimeError, match="not supported"):
        native_module()._target()


def test_explicit_rebuild_uses_toolchain_and_preserves_last_good_build_on_failure(monkeypatch, tmp_path):
    module = build_module()
    cached = record_build(b"synthetic-last-good-build")
    monkeypatch.setattr(module.shutil, "which", Mock(return_value="/synthetic/go"))
    compiler = Mock(return_value=Mock(returncode=0, stdout="go version go1.27.2 fixture/fixture", stderr=""))
    monkeypatch.setattr(module.subprocess, "run", compiler)
    monkeypatch.setattr(module.httpx, "stream", Mock(return_value=downloaded(b"untrusted-archive")))
    with pytest.raises(RuntimeError, match="checksum"):
        module.build_native_library(tmp_path / "installed", rebuild=True)
    compiler.assert_called_once()
    assert cached.read_bytes() == b"synthetic-last-good-build"
    assert native_module().native_library_asset().sha256 == hashlib.sha256(cached.read_bytes()).hexdigest()


@pytest.mark.parametrize("failure", ["export", "registration"])
def test_failed_export_preserves_last_registered_native_build(monkeypatch, tmp_path, failure):
    module = build_module()
    old = b"synthetic-last-good-code"
    record_build(old)
    installed = module.build_native_library(tmp_path / "installed")
    previous = native_module().native_library_asset()

    def fetch(source, destination):
        (destination / "cffi_src").mkdir(parents=True)
        (destination / "http2").mkdir()

    def run(args, work, environment, stage):
        if stage == "toolchain check":
            return "go version go1.27.2 fixture/fixture"
        if stage == "peer test selection":
            return (
                '{"Dir": ' + __import__("json").dumps(str(work / "fhttp" / "http2")) + ', "GoFiles": ["transport.go"]}'
            )
        if stage == "compilation":
            Path(args[args.index("-o") + 1]).write_bytes(b"synthetic-new-valid-code")
        return ""

    monkeypatch.setattr(module.shutil, "which", Mock(return_value="/synthetic/go"))
    monkeypatch.setattr(module, "_fetch_source", fetch)
    monkeypatch.setattr(module, "_apply_patches", lambda work: None)
    monkeypatch.setattr(module, "_run", run)
    operation = "_atomic_write" if failure == "export" else "_record_build"
    monkeypatch.setattr(module, operation, Mock(side_effect=OSError("Synthetic failed deployment export")))
    with pytest.raises(OSError, match="export"):
        module.build_native_library(tmp_path / "installed", rebuild=True)
    assert native_module().native_library_asset() == previous
    assert installed.read_bytes() == old
