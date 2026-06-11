import re
from pathlib import Path

from ...exceptions import FileParsingError


def read_mcfunction_file(path: str | Path) -> dict[str, str]:
    path = Path(path)
    data = {}
    try:
        with path.open(encoding="utf-8") as file:
            lines = file.readlines()

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if "data modify storage" in line and "set value" in line:
                match = re.search(r'set value "([^"\\]*(?:\\.[^"\\]*)*)"', line)
                if match:
                    text = match.group(1)
                    text = text.replace('\\"', '"')
                    key = f"{path}:{line_num}"
                    data[key] = text
        return data
    except OSError as e:
        raise FileParsingError(f"Cannot read {path}: {e}") from e


def write_mcfunction_file(original_path: str | Path, translated_data: dict[str, str]) -> None:
    original_path = Path(original_path)
    try:
        with original_path.open(encoding="utf-8") as file:
            lines = file.readlines()

        for line_num, line in enumerate(lines):
            original_line = line.strip()
            if "data modify storage" in original_line and "set value" in original_line:
                key = f"{original_path}:{line_num + 1}"
                if key in translated_data:
                    translated_text = translated_data[key]
                    escaped_text = translated_text.replace('"', '\\"')
                    new_line = re.sub(
                        r'(set value )"([^"\\]*(?:\\.[^"\\]*)*)"',
                        f'\\1"{escaped_text}"',
                        line,
                    )
                    lines[line_num] = new_line

        with original_path.open("w", encoding="utf-8") as file:
            file.writelines(lines)
    except OSError as e:
        raise FileParsingError(f"Cannot write {original_path}: {e}") from e
