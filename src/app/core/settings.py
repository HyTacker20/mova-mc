from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any


class Settings:
    def __init__(
        self,
        cli_args: argparse.Namespace | None = None,
        config_data: dict[str, Any] | None = None,
    ) -> None:
        self.source_mc_lang = self._format_lang("en_US")
        self.target_mc_lang = self._format_lang("es_ES")
        self.mods_path: str = "./"
        self._temp_path: str | None = None
        self.translation_path: str = "./translated_mods"
        self.provider = "google"
        self.max_workers = 4
        self.dry_run = False
        self.debug = False
        self.include_mods: list[str] | None = None
        self.exclude_mods: list[str] | None = None
        self.selected_mods: list[str] | None = None
        self.no_cache: bool = False
        self.hint_lang: str | None = None
        self.glossary_path: str | None = None
        self.model: str | None = None
        self.output_mode: str = "separate"  # "replace" or "separate"
        self.qa_judge: bool = False
        self.qa_judge_provider: str | None = None
        self.qa_judge_model: str | None = None
        self.qa_corrector_model: str | None = None
        self.qa_threshold: int = 3
        self.qa_max_attempts: int = 2
        self.qa_streaming: bool = True
        self.qa_chunk_size: int = 25
        self.qa_judge_workers: int = 2
        self.chunk_mode: str = "auto"
        self.chunk_size: int | None = None
        self.progress_batch_size: int = 10
        self.rate_limit_rpm: float | None = None
        self.rate_limit_burst: float | None = None
        self.rate_limit_services: dict[str, dict[str, float]] = {}

        if config_data:
            self._apply_config_data(config_data)

        if cli_args:
            self._apply_cli_args(cli_args)

        self.source_google_lang = self._get_google_lang(self.source_mc_lang)
        self.target_google_lang = self._get_google_lang(self.target_mc_lang)

    @property
    def temp_path(self) -> str:
        """Return the temp workspace path, lazily creating a unique directory.

        On first access (when no explicit value was set), creates a unique
        directory via ``tempfile.mkdtemp(prefix=\"mmt_\")`` under the system
        temp directory.  This prevents accidental deletion of a user's own
        ``./temp/`` folder.
        """
        if self._temp_path is None:
            self._temp_path = tempfile.mkdtemp(prefix="mmt_")
        return self._temp_path

    @temp_path.setter
    def temp_path(self, value: str) -> None:
        self._temp_path = value

    def _apply_config_data(self, config_data: dict[str, Any]) -> None:
        if config_data.get("source"):
            self.source_mc_lang = self._format_lang(config_data["source"])
        if config_data.get("target"):
            self.target_mc_lang = self._format_lang(config_data["target"])
        if config_data.get("provider"):
            self.provider = config_data["provider"]
        if "workers" in config_data and config_data["workers"] is not None:
            self.max_workers = int(config_data["workers"])
        if config_data.get("output"):
            self.translation_path = config_data["output"]
        if config_data.get("path"):
            self.mods_path = config_data["path"]
        if "hint_lang" in config_data and config_data["hint_lang"] is not None:
            self.hint_lang = self._format_lang(config_data["hint_lang"])
        if "glossary_path" in config_data and config_data["glossary_path"] is not None:
            self.glossary_path = config_data["glossary_path"]
        if "no_cache" in config_data:
            self.no_cache = bool(config_data["no_cache"])
        if "model" in config_data and config_data["model"] is not None:
            self.model = str(config_data["model"])
        if "output_mode" in config_data:
            self.output_mode = config_data["output_mode"]
        mods_config = config_data.get("mods", {})
        if isinstance(mods_config, dict):
            if "include" in mods_config:
                self.include_mods = mods_config["include"]
            if "exclude" in mods_config:
                self.exclude_mods = mods_config["exclude"]

        # QA config — flat keys or under a [qa] table
        qa_config = config_data.get("qa", {})
        if isinstance(qa_config, dict):
            if "judge" in qa_config:
                self.qa_judge = bool(qa_config["judge"])
            if "judge_provider" in qa_config:
                self.qa_judge_provider = str(qa_config["judge_provider"])
            if "judge_model" in qa_config:
                val = qa_config["judge_model"]
                if isinstance(val, str) and val in ("Select.NULL", "Select.BLANK", ""):
                    self.qa_judge_model = None
                else:
                    self.qa_judge_model = str(val)
            if "corrector_model" in qa_config:
                self.qa_corrector_model = str(qa_config["corrector_model"])
            if "threshold" in qa_config:
                self.qa_threshold = int(qa_config["threshold"])
            if "max_attempts" in qa_config:
                self.qa_max_attempts = int(qa_config["max_attempts"])
            if "streaming" in qa_config:
                self.qa_streaming = bool(qa_config["streaming"])
            if "chunk_size" in qa_config:
                self.qa_chunk_size = int(qa_config["chunk_size"])
            if "judge_workers" in qa_config:
                self.qa_judge_workers = int(qa_config["judge_workers"])
        # Also check flat keys for backward compatibility
        if "qa_judge" in config_data:
            self.qa_judge = bool(config_data["qa_judge"])
        if "qa_judge_provider" in config_data:
            self.qa_judge_provider = str(config_data["qa_judge_provider"])
        if "qa_judge_model" in config_data:
            val = config_data["qa_judge_model"]
            if isinstance(val, str) and val in ("Select.NULL", "Select.BLANK", ""):
                self.qa_judge_model = None
            else:
                self.qa_judge_model = str(val)
        if "qa_corrector_model" in config_data:
            self.qa_corrector_model = str(config_data["qa_corrector_model"])
        if "qa_threshold" in config_data:
            self.qa_threshold = int(config_data["qa_threshold"])
        if "qa_max_attempts" in config_data:
            self.qa_max_attempts = int(config_data["qa_max_attempts"])

        if "chunk_mode" in config_data:
            self.chunk_mode = str(config_data["chunk_mode"])
        if "chunk_size" in config_data and config_data["chunk_size"] is not None:
            self.chunk_size = int(config_data["chunk_size"])
        if "progress_batch_size" in config_data:
            self.progress_batch_size = int(config_data["progress_batch_size"])

        rate_limit_config = config_data.get("rate_limit", {})
        if isinstance(rate_limit_config, dict):
            if "rpm" in rate_limit_config:
                self.rate_limit_rpm = float(rate_limit_config["rpm"])
            if "burst" in rate_limit_config:
                self.rate_limit_burst = float(rate_limit_config["burst"])
            for key, value in rate_limit_config.items():
                if key in ("rpm", "burst") or not isinstance(value, dict):
                    continue
                service_cfg: dict[str, float] = {}
                if "rpm" in value:
                    service_cfg["rpm"] = float(value["rpm"])
                if "burst" in value:
                    service_cfg["burst"] = float(value["burst"])
                if service_cfg:
                    self.rate_limit_services[str(key).lower()] = service_cfg

    def _apply_cli_args(self, cli_args: argparse.Namespace) -> None:
        if hasattr(cli_args, "source") and cli_args.source:
            self.source_mc_lang = self._format_lang(cli_args.source)

        if hasattr(cli_args, "target") and cli_args.target:
            self.target_mc_lang = self._format_lang(cli_args.target)

        if hasattr(cli_args, "path") and cli_args.path:
            self.mods_path = cli_args.path

        if hasattr(cli_args, "output") and cli_args.output:
            self.translation_path = cli_args.output

        if hasattr(cli_args, "provider") and cli_args.provider:
            self.provider = cli_args.provider

        if hasattr(cli_args, "ai") and cli_args.ai:
            self.provider = "openai"

        if hasattr(cli_args, "workers"):
            self.max_workers = cli_args.workers

        if hasattr(cli_args, "dry_run"):
            self.dry_run = cli_args.dry_run

        if hasattr(cli_args, "include_mods") and cli_args.include_mods:
            self.include_mods = cli_args.include_mods.split(",")
        if hasattr(cli_args, "exclude_mods") and cli_args.exclude_mods:
            self.exclude_mods = cli_args.exclude_mods.split(",")
        if hasattr(cli_args, "selected_mods") and cli_args.selected_mods:
            self.selected_mods = cli_args.selected_mods

        if hasattr(cli_args, "no_cache") and cli_args.no_cache:
            self.no_cache = True

        if hasattr(cli_args, "hint_lang") and cli_args.hint_lang:
            self.hint_lang = self._format_lang(cli_args.hint_lang)

        if hasattr(cli_args, "glossary_path") and cli_args.glossary_path:
            self.glossary_path = cli_args.glossary_path

        if hasattr(cli_args, "model") and cli_args.model:
            self.model = cli_args.model

        if hasattr(cli_args, "output_mode") and cli_args.output_mode:
            self.output_mode = cli_args.output_mode

        if hasattr(cli_args, "mods_list") and cli_args.mods_list:
            try:
                with Path(cli_args.mods_list).open(encoding="utf-8") as f:
                    self.selected_mods = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except OSError:
                pass

        # QA CLI flags
        if hasattr(cli_args, "qa_judge") and cli_args.qa_judge:
            self.qa_judge = True
        if hasattr(cli_args, "qa_judge_provider") and cli_args.qa_judge_provider:
            self.qa_judge_provider = cli_args.qa_judge_provider
        if hasattr(cli_args, "qa_judge_model") and cli_args.qa_judge_model:
            self.qa_judge_model = cli_args.qa_judge_model
        if hasattr(cli_args, "qa_corrector_model") and cli_args.qa_corrector_model:
            self.qa_corrector_model = cli_args.qa_corrector_model
        if hasattr(cli_args, "qa_threshold") and cli_args.qa_threshold is not None:
            self.qa_threshold = int(cli_args.qa_threshold)
        if hasattr(cli_args, "qa_max_attempts") and cli_args.qa_max_attempts is not None:
            self.qa_max_attempts = int(cli_args.qa_max_attempts)

    def _get_google_lang(self, mc_lang: str) -> str:
        google_lang = mc_lang.split("_")[0]
        return google_lang

    def _format_lang(self, mc_lang: str) -> str:
        if not isinstance(mc_lang, str) or not mc_lang.strip():
            return mc_lang
        parts = mc_lang.split("_")
        if len(parts) == 1:
            return parts[0].lower()
        language, region = parts[0], parts[-1]
        return f"{language.lower()}_{region.upper()}"

    def effective_output_path(self) -> str:
        """Return the directory where translated JARs should be written.

        In ``replace`` mode output goes to ``mods_path`` (in-place).
        In ``separate`` mode output goes to ``translation_path``.
        """
        if self.output_mode == "replace":
            return self.mods_path
        return self.translation_path
