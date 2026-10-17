from __future__ import annotations

from typing import Any, Literal

VizType = Literal["card", "table", "line", "bar", "map", "heatmap"]


def generate_visualization(
    viz_type: VizType,
    title: str,
    data: list[dict[str, Any]],
    *,
    x: str | None = None,
    y: str | list[str] | None = None,
    units: str | None = None,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    if not columns and data:
        columns = list(data[0].keys())

    return {
        "type": viz_type,
        "title": title,
        "data": data,
        "x": x,
        "y": y,
        "units": units,
        "columns": columns,
    }
