"""Small formatting and styling helpers shared by risk-management charts."""

import numpy as np


def format_number(value):
    return f"{value:,.0f}" if abs(value) >= 10 else f"{value:,.2f}"


def color_table_by_sign(table, values):
    """Color data cells by sign.

    values is shaped as table rows by scenario columns.
    """

    max_abs = np.nanmax(np.abs(values)) if values.size else 1
    if max_abs == 0 or not np.isfinite(max_abs):
        max_abs = 1

    for row_index in range(values.shape[0]):
        for col_index in range(values.shape[1]):
            value = values[row_index, col_index]
            intensity = min(abs(value) / max_abs, 1)
            if value >= 0:
                color = (0.86 - 0.16 * intensity, 0.95, 0.89 - 0.12 * intensity)
            else:
                color = (0.98, 0.86 - 0.18 * intensity, 0.84 - 0.16 * intensity)
            table[(row_index + 1, col_index)].set_facecolor(color)


def color_risk_matrix_table(table, table_rows, values):
    """Color P&L by sign and Greeks by exposure type."""

    row_palettes = {
        "delta": (0.86, 0.92, 0.99),
        "gamma": (0.88, 0.96, 0.91),
        "theta": (0.99, 0.93, 0.84),
        "vega": (0.93, 0.90, 0.98),
        "rho": (0.90, 0.95, 0.95),
    }
    for row_index, row_name in enumerate(table_rows):
        row_values = values[row_index]
        max_abs = np.nanmax(np.abs(row_values)) if row_values.size else 1
        if max_abs == 0 or not np.isfinite(max_abs):
            max_abs = 1
        for col_index, value in enumerate(row_values):
            intensity = min(abs(value) / max_abs, 1)
            if row_name == "pnl":
                if value >= 0:
                    color = (0.86 - 0.16 * intensity, 0.95, 0.89 - 0.12 * intensity)
                else:
                    color = (0.98, 0.86 - 0.18 * intensity, 0.84 - 0.16 * intensity)
            else:
                base = row_palettes.get(row_name, (0.93, 0.93, 0.93))
                color = tuple(max(channel - 0.18 * intensity, 0.55) for channel in base)
            table[(row_index + 1, col_index)].set_facecolor(color)
