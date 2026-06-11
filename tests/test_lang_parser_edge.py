from pathlib import Path

import pytest

from app.exceptions import FileParsingError
from app.infrastructure.parsers.lang_parser import read_lang_file


class TestLangParserEdge:
    def test_read_lang_file_with_blank_lines_and_comments(self, tmp_path: Path):
        content = "# This is a comment\n\nitem.diamond.name=Diamond\n\n# Another comment\nitem.gold.name=Gold\n\n"
        path = tmp_path / "en_US.lang"
        path.write_text(content, encoding="utf-8")
        data = read_lang_file(str(path))
        assert data["item.diamond.name"] == "Diamond"
        assert data["item.gold.name"] == "Gold"
        assert "#" not in data
        assert len(data) == 2

    def test_read_lang_file_not_found(self):
        with pytest.raises(FileParsingError):
            read_lang_file("/nonexistent/path/file.lang")
