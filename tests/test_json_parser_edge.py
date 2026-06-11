from pathlib import Path

import pytest

from app.exceptions import FileParsingError
from app.infrastructure.parsers.json_parser import parse_json_with_comments


class TestJsonParserEdge:
    def test_parse_json_invalid_syntax(self, tmp_path: Path):
        path = tmp_path / "broken.json"
        path.write_text('{"key": "value", broken}', encoding="utf-8")
        with pytest.raises(FileParsingError):
            parse_json_with_comments(str(path))

    def test_parse_json_preserves_urls(self, tmp_path: Path):
        path = tmp_path / "urls.json"
        path.write_text('{"url": "https://example.com/path", "value": 1 // comment\n}', encoding="utf-8")
        data = parse_json_with_comments(str(path))
        assert data["url"] == "https://example.com/path"
        assert data["value"] == 1
