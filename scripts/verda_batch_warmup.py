"""Warm up local drawing page rendering and write a timing report.

This script only calls the local ``agent.drawings.page_png`` function. It does not
call Gemini, Nemotron, Verda, or any other online API.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import config, drawings

SUPPORTED = drawings.IMAGE_EXT | drawings.PDF_EXT
DEFAULT_LIMIT = 30
REPORT_PATH = Path(__file__).resolve().parents[1] / "docs" / "verda-benchmark.md"


def discover_drawings() -> list[str]:
    """Return supported image/PDF paths relative to DATA_DIR, in stable order."""
    if not config.DATA_DIR.is_dir():
        return []
    return sorted(
        path.relative_to(config.DATA_DIR).as_posix()
        for path in config.DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED
    )


def render_report(rows: list[dict[str, object]], data_dir: Path) -> str:
    lines = [
        "# Verda 本地图纸预热基准",
        "",
        f"- 生成时间（UTC）：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- DATA_DIR：由环境变量配置（具体路径未写入报告）。",
        f"- 图纸数：{len(rows)}",
        "- 执行方式：本地调用 `agent.drawings.page_png`；未调用在线 API。",
        "",
        "| 图纸（相对 DATA_DIR） | 页码 | 耗时（秒） | 输出 PNG | 结果 |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        path = str(row["path"]).replace("|", "\\|")
        output = str(row.get("output", "")).replace("|", "\\|")
        error = str(row.get("error", "")).replace("|", "\\|").replace("\n", " ")
        result = "完成" if not error else f"失败：{error}"
        elapsed = row.get("elapsed", 0.0)
        lines.append(f"| `{path}` | {row['page']} | {elapsed:.6f} | `{output}` | {result} |")
    if not rows:
        lines.append("| — | — | — | — | 未找到可处理图纸 |")
    lines.extend(["", "该报告仅记录本地预渲染耗时，不是 Verda 云端性能或成本数据。", ""])
    return "\n".join(lines)


def run(paths: list[str], page: int, limit: int) -> list[dict[str, object]]:
    if not 1 <= limit <= DEFAULT_LIMIT:
        raise ValueError(f"--limit must be between 1 and {DEFAULT_LIMIT}")
    if page < 1:
        raise ValueError("--page must be at least 1")
    selected = paths or discover_drawings()
    if len(selected) > DEFAULT_LIMIT:
        raise ValueError(f"at most {DEFAULT_LIMIT} drawings may be selected (received {len(selected)})")
    selected = selected[:limit]
    rows: list[dict[str, object]] = []
    for path in selected:
        started = perf_counter()
        try:
            png = drawings.page_png(path, page)
            output = str(png.relative_to(config.DATA_DIR) if png.is_relative_to(config.DATA_DIR) else (png.relative_to(REPO_ROOT) if png.is_relative_to(REPO_ROOT) else Path(png.name)))
            rows.append({"path": path, "page": page, "elapsed": perf_counter() - started, "output": output})
        except Exception as exc:  # Record per-file failures and continue the batch.
            rows.append({"path": path, "page": page, "elapsed": perf_counter() - started,
                         "output": "", "error": f"{type(exc).__name__}: {exc}"})
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(rows, config.DATA_DIR), encoding="utf-8")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="dataset-relative image/PDF paths; omit to discover them under DATA_DIR")
    parser.add_argument("--page", type=int, default=1, help="1-based PDF page (default: 1; images ignore it)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="maximum drawings to render (1–30)")
    args = parser.parse_args()
    try:
        rows = run(args.paths, args.page, args.limit)
    except ValueError as exc:
        parser.error(str(exc))
    for row in rows:
        status = "OK" if "error" not in row else str(row["error"])
        print(f"{row['path']}: {row['elapsed']:.6f}s — {status}")
    print(f"Wrote {REPORT_PATH}")
    return 0 if all("error" not in row for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())