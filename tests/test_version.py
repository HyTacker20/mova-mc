from app.__version__ import VERSION, __version__


class TestVersion:
    def test_version_string(self):
        parts = __version__.split(".")
        assert len(parts) == 3
        for p in parts:
            assert p.isdigit()

    def test_version_tuple(self):
        assert len(VERSION) == 3
        expected = ".".join(map(str, VERSION))
        assert __version__ == expected
