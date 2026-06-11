<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--NC%204.0-blue.svg" alt="Ліцензія"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python"></a>
</p>

# MovaMC

Інструмент для перекладу модифікацій Minecraft на різні мови, що автоматизує процес локалізації для розробників модів і перекладачів.

## Можливості

- **Автоматичний переклад** — переклад JAR-модів через Textual TUI або CLI
- **AI-переклад** — OpenAI, Anthropic, Gemini, Ollama, OpenCode Go, OpenAI-сумісні API
- **JAR pipeline** — розпакування, переклад LANG/JSON/MCFUNCTION і повторна збірка модів
- **Декілька сервісів перекладу** — Google Translate (безкоштовно) або AI-провайдери з SQLite-кешем
- **Пакетна обробка** — переклад окремих файлів, тек модів або вибір модів у TUI
- **uk_UA QA** — опційний inline LLM-суддя з tiered fix acceptance для української цілі

## Провайдери перекладу

| Провайдер | Прапорець | Вартість | Вимоги |
|---|---|---|---|
| Google Translate | `--provider google` | Безкоштовно | Пакет `deep-translator` |
| OpenAI | `--provider openai` | Платний | `OPENAI_API_KEY` |
| Anthropic Claude | `--provider anthropic` | Платний | `ANTHROPIC_API_KEY` |
| Google Gemini | `--provider gemini` | Платний/Безкоштовний | `GEMINI_API_KEY` |
| Ollama (Локальний) | `--provider ollama` | Безкоштовно | Ollama запущено локально |
| OpenCode Go | `--provider opencode` | Платний ($5–10/міс) | `OPENCODE_GO_API_KEY` |
| OpenAI-Сумісний | `--provider openaicompatible` | Залежить | `OPENAICOMPATIBLE_API_KEY` + `OPENAICOMPATIBLE_BASE_URL` |

## Встановлення

### Готові виконувані файли

Завантажте готові виконувані файли зі сторінки релізів:

- **Версія застосунку** — `MovaMC.exe` (інтерактивний застосунок)
- **Версія CLI** — `mova.exe` (інтерфейс командного рядка)

Встановлення Python не потрібне.

### З вихідного коду

```bash
# Спочатку встановіть uv (https://docs.astral.sh/uv/getting-started/installation/)
git clone git@github.com:HyTacker20/mova-mc.git
cd mova-mc

# Налаштування середовища (Windows)
scripts\setup.bat
# Або для Linux/Mac
./scripts/setup.sh

# Для підтримки AI-перекладу встановіть додаткові залежності:
uv sync --extra ai

# Запуск застосунку (Windows)
scripts\start.bat
# Або для Linux/Mac
./scripts/start.sh
```

## Конфігурація

Скопіюйте `.env.example` у `.env` та налаштуйте API ключі:

```bash
cp .env.example .env
```

Підтримувані змінні середовища:

| Змінна | Провайдер | Обов'язково | За замовчуванням |
|---|---|---|---|
| `TRANSLATION_MODEL` | Усі AI | Ні | `gpt-4o-mini` |
| `OPENAI_API_KEY` | openai | Так | — |
| `OPENAI_MODEL` | openai | Ні | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | anthropic | Так | — |
| `GEMINI_API_KEY` | gemini | Так | — |
| `OLLAMA_API_BASE` | ollama | Ні | `http://localhost:11434` |
| `OPENAICOMPATIBLE_API_KEY` | openaicompatible | Так | — |
| `OPENAICOMPATIBLE_BASE_URL` | openaicompatible | Так | — |
| `OPENAICOMPATIBLE_MODEL` | openaicompatible | Ні | `gpt-4o-mini` |
| `OPENCODE_GO_API_KEY` | opencode | Так | — |
| `OPENCODE_GO_MODEL` | opencode | Ні | `deepseek-v4-flash` |
| `OPENCODE_GO_BASE_URL` | opencode | Ні | `https://opencode.ai/zen/go/v1` |

## Використання

### Веб-інтерфейс (за замовчуванням)

```bash
mova                    # запускає веб-інтерфейс на http://127.0.0.1:8000
mova --port 3000        # на іншому порту
mova --dev              # з CORS для Vite dev-сервера
mova --no-browser       # без автоматичного відкриття браузера
```

### Інтерактивний режим (TUI)

```bash
mova tui
```

### Інтерфейс командного рядка

```bash
# Базове використання з Google Translate (безкоштовно)
mova cli --path path/to/mods --source en_US --target uk_UA --output path/to/output

# AI-переклад з OpenAI (потрібен API ключ)
mova cli --path path/to/mods --source en_US --target uk_UA --output path/to/output --provider openai

# Використання Anthropic Claude
mova cli --path path/to/mods --source en_US --target uk_UA --output path/to/output --provider anthropic

# Використання Google Gemini
mova cli --path path/to/mods --source en_US --target uk_UA --output path/to/output --provider gemini

# Використання локального Ollama
mova cli --path path/to/mods --source en_US --target uk_UA --output path/to/output --provider ollama

# Попередній перегляд (dry-run)
mova cli --path path/to/mods --source en_US --target uk_UA --dry-run

# Параметри:
# --path (-p): Шлях до моду або теки з модами (за замовчуванням: ./mods)
# --source (-s): Код вихідної мови (напр., en_US)
# --target (-t): Код цільової мови (напр., uk_UA)
# --output (-o): Шлях до вихідної теки (якщо збігається з текою модів, замінить оригінальні моди)
# --provider: Провайдер перекладу (google, openai, anthropic, gemini, ollama, openaicompatible, opencode)
# --workers: Кількість одночасних потоків перекладу (за замовчуванням: 4)
# --dry-run: Показати, що буде перекладено, без внесення змін
# --debug (-d): Увімкнути debug-логування
```

> Прапорець `--ai` застарілий. Використовуйте `--provider openai` натомість.

## Розробка

### Налаштування

```bash
uv sync                # Встановити основні залежності
uv sync --extra ai     # Встановити залежності AI-провайдерів
uv sync --group dev    # Встановити інструменти розробки (pytest, ruff, mypy)
```

### Команди

```bash
uv run pytest              # Запуск тестів
uv run pytest --cov        # Запуск тестів з покриттям
uv run ruff check .        # Лінтинг
uv run ruff format .       # Форматування
uv run mypy src/           # Перевірка типів
```

### Структура проекту

```
src/app/
  core/            Settings, Translator, FileManager, перевірки провайдерів
  services/        Провайдери перекладу (Google, OpenAI, LiteLLM та ін.)
  parsers/         Парсери файлів (JSON, LANG, MCFUNCTION)
  commands/        CLI точки входу та TUI застосунок
  utils/           Логіка повторів, обмеження запитів, звітування прогресу
tests/             Набір тестів Pytest
scripts/           Скрипти збірки та налаштування
```

## Ліцензія

Цей проект ліцензовано відповідно до [Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)](LICENSE).
