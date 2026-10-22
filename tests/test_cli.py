import subprocess
import sys

from PIL import Image

from conftest import QUADRANT_COLOURS, SIZE


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "tiff2png", *map(str, args)],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=120,
    )


def pixel(path, xy):
    with Image.open(path) as image:
        return image.convert("RGB").getpixel(xy)


def test_fill_gives_exact_size(tiff, tmp_path):
    out = tmp_path / "out"
    result = run_cli(tiff("rgb"), "-o", out, "--fill", "64x48", "--scale", "50")
    assert result.returncode == 0, result.stderr
    with Image.open(out / "Batch_01.png") as image:
        assert image.size == (64, 48)


def test_fill_gives_exact_non_native_aspect(tiff, tmp_path):
    out = tmp_path / "out"
    result = run_cli(tiff("rgb"), "-o", out, "--fill", "20x30")
    assert result.returncode == 0, result.stderr
    with Image.open(out / "Batch_01.png") as image:
        assert image.size == (20, 30)


def test_crop_changes_pixels(tiff, tmp_path):
    out = tmp_path / "out"
    width, height = SIZE
    result = run_cli(
        tiff("quadrants"), "-o", out, "--fill", "16x12",
        "--crop", f"{width // 2},{height // 2},{width},{height}",
        "--resample", "nearest",
    )
    assert result.returncode == 0, result.stderr
    assert pixel(out / "Batch_01.png", (8, 6)) == QUADRANT_COLOURS["br"]
    centred = tmp_path / "centred"
    run_cli(tiff("quadrants"), "-o", centred, "--fill", "16x12", "--resample", "nearest")
    assert pixel(centred / "Batch_01.png", (1, 1)) != pixel(out / "Batch_01.png", (1, 1))


def test_all_pages_suffixes(tiff, tmp_path):
    out = tmp_path / "out"
    result = run_cli(tiff("multipage"), "-o", out, "--all-pages", "--naming", "original")
    assert result.returncode == 0, result.stderr
    names = sorted(path.name for path in out.iterdir())
    assert names == ["multipage_p01.png", "multipage_p02.png", "multipage_p03.png"]
    colours = [pixel(out / name, (0, 0)) for name in names]
    assert colours == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


def test_first_page_only_has_no_suffix(tiff, tmp_path):
    out = tmp_path / "out"
    result = run_cli(tiff("multipage"), "-o", out, "--naming", "original")
    assert result.returncode == 0, result.stderr
    assert [path.name for path in out.iterdir()] == ["multipage.png"]


def test_folder_with_corrupt_file_exits_1(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    Image.new("RGB", (8, 8), "red").save(folder / "x.TIF")
    Image.new("RGB", (8, 8), "blue").save(folder / "y.tiff")
    (folder / "bad.tif").write_bytes(b"this is not a tiff")
    (folder / "notes.txt").write_text("ignored")
    out = tmp_path / "out"
    result = run_cli(folder, "-o", out, "--naming", "original")
    assert result.returncode == 1
    assert sorted(path.name for path in out.iterdir()) == ["x.png", "y.png"]
    assert "bad.tif" in result.stderr
    assert "2 converted, 1 failed" in result.stderr


def test_naming_original(tiff, tmp_path):
    out = tmp_path / "out"
    result = run_cli(tiff("rgb"), tiff("l"), "-o", out, "--naming", "original")
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in out.iterdir()) == ["l.png", "rgb.png"]


def test_naming_root(tiff, tmp_path):
    out = tmp_path / "out"
    result = run_cli(tiff("rgb"), tiff("l"), "-o", out, "--naming", "root", "--root", "out")
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in out.iterdir()) == ["out_01.png", "out_02.png"]


def test_existing_output_without_overwrite_exits_2(tiff, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "rgb.png"
    existing.write_bytes(b"precious")
    result = run_cli(tiff("rgb"), tiff("l"), "-o", out, "--naming", "original")
    assert result.returncode == 2
    assert existing.read_bytes() == b"precious"
    assert [path.name for path in out.iterdir()] == ["rgb.png"]


def test_overwrite_replaces(tiff, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "rgb.png"
    existing.write_bytes(b"old")
    result = run_cli(tiff("rgb"), "-o", out, "--naming", "original", "--overwrite")
    assert result.returncode == 0, result.stderr
    with Image.open(existing) as image:
        assert image.size == SIZE


def test_case_collision_exits_2(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    Image.new("RGB", (8, 8), "red").save(folder / "a.tif")
    Image.new("RGB", (8, 8), "blue").save(folder / "a.TIFF")
    out = tmp_path / "out"
    result = run_cli(folder, "-o", out, "--naming", "original")
    assert result.returncode == 2
    assert "collide" in result.stderr
    assert not out.exists()


def test_usage_errors_exit_2(tiff, tmp_path):
    assert run_cli(tmp_path / "missing.tif").returncode == 2
    assert run_cli(tiff("rgb"), "--scale", "0").returncode == 2
    assert run_cli(tiff("rgb"), "--crop", "0,0,8,8").returncode == 2
    assert run_cli(tiff("rgb"), "--fit", "10x10", "--fill", "10x10").returncode == 2
    assert run_cli(tiff("rgb"), "--compress-level", "12").returncode == 2


def test_default_output_is_input_folder(tiff, tiff_dir):
    result = run_cli(tiff("rgb"), "--naming", "original")
    assert result.returncode == 0, result.stderr
    assert (tiff_dir / "rgb.png").exists()


def test_help_exits_0():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "--overwrite" in result.stdout
