"""Dashboard data + chart helpers (baseline panels + chart from orchestrator result)."""

from src.dashboard.chart_from_result import tabular_result_to_chart
from src.dashboard.chart_specs import ChartSpec, default_dashboard_specs
from src.dashboard.data_service import load_all_panel_data
from src.dashboard.plotly_render import figures_for_dashboard

__all__ = [
    "ChartSpec",
    "default_dashboard_specs",
    "load_all_panel_data",
    "figures_for_dashboard",
    "tabular_result_to_chart",
]
