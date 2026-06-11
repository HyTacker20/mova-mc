from pathlib import Path

from ...exceptions import FileParsingError


def read_lang_file(path: str | Path) -> dict[str, str]:
    path = Path(path)
    data = {}
    try:
        with path.open(encoding="utf-8") as file:
            lines = file.readlines()
    except OSError as e:
        raise FileParsingError(f"Cannot read {path}: {e}") from e

    for line in lines:
        line = line.strip()
        if line:
            try:
                key, value = line.split("=", 1)
                data[key] = value
            except ValueError:
                pass
    return data


def write_lang_file(data: dict[str, str], path: str | Path) -> None:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ""
        for key, value in data.items():
            # .lang format requires each entry on one line (key=value).
            # Actual newlines would break the format, so replace them with
            # literal \n tokens to match Minecraft's escape convention.
            value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
            text += f"{key}={value}\n"
        with path.open("w", encoding="utf-8") as file:
            file.write(text)
    except OSError as e:
        raise FileParsingError(f"Cannot write {path}: {e}") from e
