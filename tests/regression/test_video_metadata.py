import builtins
import contextlib
import importlib
import importlib.metadata
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest


def _box(name: str, payload: bytes) -> bytes:
    return struct.pack(">I4s", len(payload) + 8, name.encode("ascii")) + payload


def _sample_mp4(width: int = 720, height: int = 1280, duration: float = 3.5) -> bytes:
    timescale = 1000
    duration_units = int(duration * timescale)
    ftyp = _box("ftyp", b"isom\x00\x00\x00\x01isommp42")

    mvhd = _box(
        "mvhd",
        b"\x00\x00\x00\x00" + b"\x00" * 8 + struct.pack(">II", timescale, duration_units),
    )
    tkhd_payload = bytearray(84)
    tkhd_payload[0] = 0
    tkhd_payload[3] = 3
    struct.pack_into(">I", tkhd_payload, 76, width << 16)
    struct.pack_into(">I", tkhd_payload, 80, height << 16)
    tkhd = _box("tkhd", bytes(tkhd_payload))
    mdhd = _box(
        "mdhd",
        b"\x00\x00\x00\x00" + b"\x00" * 8 + struct.pack(">II", timescale, duration_units),
    )
    hdlr = _box("hdlr", b"\x00\x00\x00\x00" + b"\x00" * 4 + b"vide")
    mdia = _box("mdia", mdhd + hdlr)
    trak = _box("trak", tkhd + mdia)
    moov = _box("moov", mvhd + trak)
    return ftyp + moov + _box("mdat", b"\x00" * 4)


def _write_sample_mp4(folder: Path, name: str = "sample.mp4") -> Path:
    path = folder / name
    path.write_bytes(_sample_mp4())
    return path


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
    pytest.skip("ffmpeg is required for MoviePy video generation coverage")


def _write_real_mp4(folder: Path, name: str = "source.mp4", duration: float = 4.0) -> Path:
    path = folder / name
    subprocess.run(
        [
            _ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=640x360:d={duration}",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return path


def _block_moviepy_imports(exc):
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("moviepy"):
            raise exc
        return real_import(name, *args, **kwargs)

    return mock.patch("builtins.__import__", side_effect=blocked_import)


def test_mp4_metadata_parser_reads_dimensions_and_duration():
    from aiograpi.utils.video import read_video_metadata

    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_sample_mp4(Path(tmpdir))
        metadata = read_video_metadata(path)

    assert metadata.width == 720
    assert metadata.height == 1280
    assert metadata.duration == 3.5


def test_analyze_video_with_thumbnail_does_not_import_moviepy():
    import aiograpi.mixins.clip as clip_mixin
    import aiograpi.mixins.igtv as igtv_mixin
    import aiograpi.mixins.video as video_mixin

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        path = _write_sample_mp4(tmpdir)
        thumbnail = tmpdir / "thumb.jpg"
        thumbnail.write_bytes(b"thumbnail")
        with _block_moviepy_imports(AssertionError("moviepy should not be imported")):
            video_result = video_mixin.analyze_video(path, thumbnail=thumbnail)
            clip_result = clip_mixin.analyze_video(path, thumbnail=thumbnail)
            igtv_result = igtv_mixin.analyze_video(path, thumbnail=thumbnail)

    assert video_result[0:2] == (720, 1280)
    assert video_result[2] == 3.5
    assert video_result[3] == thumbnail
    assert clip_result[0] == thumbnail
    assert clip_result[1:3] == (720, 1280)
    assert clip_result[3] == 3.5
    assert igtv_result[0] == thumbnail
    assert igtv_result[1:3] == (720, 1280)
    assert igtv_result[3] == 3.5


def test_missing_thumbnail_reports_ffmpeg_fix():
    import aiograpi.mixins.video as video_mixin

    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_sample_mp4(Path(tmpdir))
        with _block_moviepy_imports(ImportError("no moviepy")):
            with pytest.raises(RuntimeError) as ctx:
                video_mixin.analyze_video(path)

    message = str(ctx.value)
    assert "thumbnail=" in message
    assert "ffmpeg" in message.lower()
    assert "IMAGEIO_FFMPEG_EXE" in message


def test_core_install_does_not_require_moviepy():
    pyproject = Path("pyproject.toml").read_text()
    required_dependencies = pyproject.split("[project.optional-dependencies]", 1)[0]
    optional_dependencies = pyproject.split("[project.optional-dependencies]", 1)[1]

    assert "moviepy" not in required_dependencies
    assert "video = [" in optional_dependencies
    assert '"imageio-ffmpeg>=0.2.0"' in optional_dependencies
    assert '"moviepy==1.0.3"' not in optional_dependencies


def test_story_builder_import_does_not_require_moviepy():
    sys.modules.pop("aiograpi.story", None)
    with _block_moviepy_imports(ImportError("no moviepy")):
        try:
            story = importlib.import_module("aiograpi.story")
        except Exception as exc:
            pytest.fail(f"StoryBuilder import should not require MoviePy: {exc}")

    assert story.StoryBuilder(Path("photo.jpg")).path == Path("photo.jpg")


def test_story_builder_render_reports_video_extra_without_moviepy():
    sys.modules.pop("aiograpi.story", None)
    with _block_moviepy_imports(ImportError("no moviepy")):
        story = importlib.import_module("aiograpi.story")
        with pytest.raises(RuntimeError) as ctx:
            story.StoryBuilder(Path("video.mp4")).video()

    message = str(ctx.value)
    assert "aiograpi[video]" in message
    assert "moviepy==2.2.1" in message
    assert "--no-deps" in message


def test_prepare_video_reports_video_extra_without_moviepy():
    from aiograpi.image_util import prepare_video

    with _block_moviepy_imports(ImportError("no moviepy")):
        with pytest.raises(RuntimeError) as ctx:
            prepare_video("video.mp4")

    message = str(ctx.value)
    assert "aiograpi[video]" in message
    assert "moviepy==2.2.1" in message
    assert "--no-deps" in message


def test_story_builder_photo_generates_video_with_moviepy_2():
    from PIL import Image

    from aiograpi.story import StoryBuilder
    from aiograpi.utils.video import read_video_metadata

    assert importlib.metadata.version("moviepy") == "2.2.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        image = tmpdir / "photo.jpg"
        Image.new("RGB", (720, 1280), "white").save(image)

        build = StoryBuilder(image).photo(max_duration=1)
        try:
            output = Path(build.path)
            assert output.exists()
            assert output.stat().st_size > 0
            metadata = read_video_metadata(output)
            assert (metadata.width, metadata.height) == (720, 1280)
            assert metadata.duration == pytest.approx(1.0, abs=0.25)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(build.path)


def test_prepare_video_generates_thumbnail_with_moviepy_2():
    from aiograpi.image_util import prepare_video

    assert importlib.metadata.version("moviepy") == "2.2.1"
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_real_mp4(Path(tmpdir))
        video_data, size, duration, thumbnail_data = prepare_video(
            str(path),
            max_size=None,
            aspect_ratios=None,
            skip_reencoding=True,
        )

    assert len(video_data) > 0
    assert size == [640, 360]
    assert duration == pytest.approx(4.0, abs=0.25)
    assert len(thumbnail_data) > 0
