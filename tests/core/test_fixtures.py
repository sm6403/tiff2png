import pytest
from PIL import Image

from conftest import FIXTURES


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_reopens_as_intended(tiff, name):
    spec = FIXTURES[name]
    with Image.open(tiff(name)) as image:
        assert image.mode == spec.mode
        assert image.size == spec.size
        assert getattr(image, "n_frames", 1) == spec.n_frames
