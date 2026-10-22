from PIL import Image

from tiff2png.core.jobs import Naming, find_tiffs, plan_jobs
from tiff2png.core.settings import Pages


def test_find_tiffs_matches_case_and_does_not_recurse(tmp_path):
    for name in ("a.tif", "b.TIFF", "c.Tif", "d.png"):
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "e.tif").write_bytes(b"")
    assert [p.name for p in find_tiffs(tmp_path)] == ["a.tif", "b.TIFF", "c.Tif"]


def test_plan_root_naming_and_no_directory_creation(tiff, tmp_path):
    out = tmp_path / "missing"
    plan = plan_jobs([tiff("rgb"), tiff("l")], out, Naming.ROOT_NN, "Shot")
    assert [job.dst.name for job in plan.jobs] == ["Shot_01.png", "Shot_02.png"]
    assert not out.exists()


def test_plan_reports_existing(tiff, tmp_path):
    (tmp_path / "rgb.png").write_bytes(b"x")
    plan = plan_jobs([tiff("rgb")], tmp_path, Naming.ORIGINAL)
    assert [job.dst.name for job in plan.existing] == ["rgb.png"]


def test_plan_all_pages_suffix_only_for_multipage(tiff, tmp_path):
    plan = plan_jobs(
        [tiff("multipage"), tiff("rgb")], tmp_path, Naming.ROOT_NN, "r", Pages.ALL
    )
    assert [(job.page, job.dst.name) for job in plan.jobs] == [
        (0, "r_01_p01.png"),
        (1, "r_01_p02.png"),
        (2, "r_01_p03.png"),
        (0, "r_02.png"),
    ]


def test_plan_collision_ignores_case(tmp_path):
    for name in ("a.tif", "a.TIFF"):
        Image.new("L", (2, 2)).save(tmp_path / name)
    plan = plan_jobs(sorted(tmp_path.iterdir()), tmp_path / "o", Naming.ORIGINAL)
    assert len(plan.collisions) == 1
    assert len(plan.collisions[0]) == 2
