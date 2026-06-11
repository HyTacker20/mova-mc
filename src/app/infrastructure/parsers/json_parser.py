from pathlib import Path
from typing import Any

import json5

from ...exceptions import FileParsingError


def remove_comments_from_json(json_str: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    length = len(json_str)

    while index < length:
        char = json_str[index]
        next_char = json_str[index + 1] if index + 1 < length else ""

        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < length and json_str[index] not in {"\n", "\r"}:
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (json_str[index] == "*" and json_str[index + 1] == "/"):
                if json_str[index] in {"\n", "\r"}:
                    result.append(json_str[index])
                index += 1
            index += 2 if index + 1 < length else 0
            continue

        result.append(char)
        index += 1

    return "".join(result)


def parse_json_with_comments(file_path: str | Path) -> dict[str, Any]:
    file_path = Path(file_path)
    try:
        with file_path.open(encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        raise FileParsingError(f"Cannot read {file_path}: {e}") from e

    try:
        return json5.loads(content, strict=False)  # type: ignore[no-any-return]
    except ValueError:
        pass

    try:
        clean_content = remove_comments_from_json(content)
        return json5.loads(clean_content)  # type: ignore[no-any-return]
    except ValueError as e:
        raise FileParsingError(f"Invalid JSON in {file_path}: {e}") from e
