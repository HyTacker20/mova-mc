from pathlib import Path

from app.infrastructure.parsers.mcfunction_parser import read_mcfunction_file


class TestMcfunctionParserEdge:
    def test_read_mcfunction_file_no_translatable_content(self, tmp_path: Path):
        content = 'tellraw @a {"text":"Hello"}\nsay Game started\nexecute as @a run function test:other\n'
        path = tmp_path / "no_translatable.mcfunction"
        path.write_text(content, encoding="utf-8")
        data = read_mcfunction_file(str(path))
        assert data == {}
