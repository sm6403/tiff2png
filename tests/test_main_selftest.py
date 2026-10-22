import tiff2png.__main__ as entry
from PIL import Image


def test_self_test_writes_rgb_png(tmp_path):
    out = tmp_path / "st.png"
    assert entry.self_test(str(out)) == 0
    with Image.open(out) as image:
        assert image.mode == "RGB"
