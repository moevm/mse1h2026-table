from __future__ import annotations

import importlib
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.csv_to_xlsx import csv_to_xlsx
from scripts.utils import error


class ExportConfigurationError(RuntimeError):
    pass


@dataclass
class ExportArtifact:
    source: str
    status: str
    csv_path: str | None = None
    xlsx_path: str | None = None
    command: list[str] = field(default_factory=list)
    cwd: str | None = None
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExportManager:
    def __init__(
        self,
        project_dir: str | Path,
        config_data: dict[str, Any] | None = None,
        config_base_dir: str | Path | None = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.config_base_dir = (
            Path(config_base_dir).resolve() if config_base_dir else self.project_dir
        )
        self.config_data = config_data or {}
        self.sources = self._extract_sources(self.config_data)

    @staticmethod
    def _extract_sources(config_data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(config_data, dict):
            return {}

        exports_section = config_data.get("exports", {})
        if isinstance(exports_section, dict) and "sources" in exports_section:
            sources = exports_section.get("sources", {})
            return sources if isinstance(sources, dict) else {}

        if isinstance(exports_section, dict):
            return exports_section

        return {}

    def _expand_templates(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, str):
            expanded = os.path.expandvars(value)
            try:
                return expanded.format_map(_SafeDict(context))
            except Exception:
                return expanded
        if isinstance(value, list):
            return [self._expand_templates(item, context) for item in value]
        if isinstance(value, dict):
            return {
                key: self._expand_templates(item, context)
                for key, item in value.items()
            }
        return value

    def _resolve_path(self, raw_path: str | None, default: Path | None = None) -> Path | None:
        if raw_path is None:
            return default
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return (self.config_base_dir / path).resolve()

    def _get_source_spec(self, source_name: str) -> dict[str, Any]:
        spec = self.sources.get(source_name)
        if spec is None:
            raise ExportConfigurationError(
                f"Источник '{source_name}' не найден в конфигурации. "
                f"Добавьте его в exports.sources."
            )
        if not isinstance(spec, dict):
            raise ExportConfigurationError(
                f"Некорректная конфигурация источника '{source_name}': ожидается словарь"
            )
        return spec

    def _build_context(
        self,
        source_name: str,
        spec: dict[str, Any],
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            **self.config_data,
            **spec,
            "source": source_name,
            "source_name": source_name,
            "project_dir": str(self.project_dir),
            "config_dir": str(self.config_base_dir),
            "python": sys.executable,
        }

        if extra_context:
            context.update(extra_context)

        mode = context.get("mode")
        mode_flags = spec.get("mode_flags", {})
        if mode and isinstance(mode_flags, dict):
            if mode not in mode_flags:
                raise ExportConfigurationError(
                    f"Для источника '{source_name}' нет mode '{mode}'. "
                    f"Доступные mode: {list(mode_flags.keys())}"
                )
            context["mode_flag"] = mode_flags[mode]

        return context

    def run(self, source_name: str, **extra_context: Any) -> ExportArtifact:
        spec = self._get_source_spec(source_name)
        context = self._build_context(source_name, spec, extra_context)
        kind = str(spec.get("kind", "subprocess")).lower().strip()

        if kind in {"subprocess", "cli", "command"}:
            artifact = self._run_subprocess(source_name, spec, context)
        elif kind in {"python", "python-callable", "callable"}:
            artifact = self._run_python_callable(source_name, spec, context)
        else:
            raise ExportConfigurationError(
                f"Неизвестный тип источника '{kind}' для '{source_name}'"
            )

        if artifact.csv_path and spec.get("build_xlsx", True):
            xlsx_tpl = spec.get("xlsx_path")
            xlsx_path = self._expand_templates(xlsx_tpl, context) if xlsx_tpl else None
            artifact.xlsx_path = csv_to_xlsx(
                artifact.csv_path,
                xlsx_path=xlsx_path,
                sheet_name=str(spec.get("xlsx_sheet_name", "Sheet1")),
            )

        return artifact

    def _run_subprocess(
        self,
        source_name: str,
        spec: dict[str, Any],
        context: dict[str, Any],
    ) -> ExportArtifact:
        command_tpl = spec.get("command")
        if not command_tpl:
            raise ExportConfigurationError(
                f"Источник '{source_name}' должен содержать поле command"
            )

        command = self._expand_templates(command_tpl, context)
        if isinstance(command, str):
            command = shlex.split(command)

        if not isinstance(command, list) or not all(isinstance(x, str) for x in command):
            raise ExportConfigurationError(
                f"command для '{source_name}' должен быть строкой или списком строк"
            )

        cwd = self._resolve_path(
            self._expand_templates(spec.get("cwd"), context),
            default=self.project_dir,
        )

        env = os.environ.copy()
        extra_env = self._expand_templates(spec.get("env", {}), context)
        if isinstance(extra_env, dict):
            env.update({str(k): str(v) for k, v in extra_env.items()})

        out_csv = self._expand_templates(spec.get("csv_path"), context)
        if not out_csv:
            raise ExportConfigurationError(
                f"Источник '{source_name}' должен содержать csv_path"
            )

        out_csv_path = self._resolve_path(str(out_csv))
        if out_csv_path and not out_csv_path.parent.exists():
            out_csv_path.parent.mkdir(parents=True, exist_ok=True)

        context["csv_path"] = str(out_csv_path)
        context["csv_abs_path"] = str(out_csv_path)
        context["csv_abs_path"] = str(out_csv_path)
        command = self._expand_templates(command, context)
        if isinstance(command, str):
            command = shlex.split(command)

        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        artifact = ExportArtifact(
            source=source_name,
            status="completed" if completed.returncode == 0 else "error",
            csv_path=str(out_csv_path),
            command=command,
            cwd=str(cwd) if cwd else None,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            meta={
                "backend": "subprocess",
                "config": spec,
            },
        )

        if completed.returncode != 0:
            error(
                f"Импорт из источника '{source_name}' завершился с кодом {completed.returncode}.\n"
                f"STDERR: {completed.stderr.strip() or '<empty>'}"
            )

        return artifact

    def _run_python_callable(
        self,
        source_name: str,
        spec: dict[str, Any],
        context: dict[str, Any],
    ) -> ExportArtifact:
        module_name = spec.get("module")
        function_name = spec.get("function")
        if not module_name or not function_name:
            raise ExportConfigurationError(
                f"Источник '{source_name}' должен содержать module и function"
            )

        module = importlib.import_module(str(module_name))
        func = getattr(module, str(function_name))

        kwargs = self._expand_templates(spec.get("kwargs", {}), context)
        if not isinstance(kwargs, dict):
            raise ExportConfigurationError(
                f"kwargs для '{source_name}' должен быть словарем"
            )

        result = func(**kwargs)

        csv_path = None
        if isinstance(result, dict):
            csv_path = result.get("csv_path")
        elif isinstance(result, str):
            csv_path = result

        if csv_path:
            csv_path = str(self._resolve_path(str(csv_path)))

        return ExportArtifact(
            source=source_name,
            status="completed",
            csv_path=csv_path,
            meta={
                "backend": "python-callable",
                "config": spec,
                "result": result,
            },
        )


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"