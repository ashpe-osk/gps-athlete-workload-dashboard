"""Accessible color tokens shared by the dashboard and Plotly charts."""
from typing import TypedDict


class ThemeColors(TypedDict):
    background: str
    surface: str
    surface_tint: str
    text: str
    muted: str
    border: str
    grid: str
    neutral_bar: str
    heatmap_mid: str
    header: str
    warning_bg: str
    warning_text: str
    kicker: str
    chart_accent: str
    rolling: str
    series: list[str]
    quality: list[str]

THEMES = {
    "Light": {
        "background": "#F4F6F8",
        "surface": "#FFFFFF",
        "surface_tint": "#FFF7ED",
        "text": "#17212B",
        "muted": "#64748B",
        "border": "#E5EAF0",
        "grid": "#E9EEF2",
        "neutral_bar": "#CBD5E1",
        "heatmap_mid": "#F8FAFC",
        "header": "rgba(244, 246, 248, 0.94)",
        "warning_bg": "#FFF4DB",
        "warning_text": "#593A00",
        "kicker": "#B45309",
        "chart_accent": "#C65D0A",
        "rolling": "#1D4ED8",
        "series": ["#C65D0A", "#2563EB", "#047857", "#7E22CE", "#BE185D", "#A16207"],
        "quality": ["#15803D", "#A16207", "#2563EB", "#C65D0A", "#DC2626"],
    },
    "Dark": {
        "background": "#101820",
        "surface": "#1B2732",
        "surface_tint": "#24313C",
        "text": "#F1F5F9",
        "muted": "#B0BEC9",
        "border": "#344451",
        "grid": "#344451",
        "neutral_bar": "#64748B",
        "heatmap_mid": "#1B2732",
        "header": "rgba(16, 24, 32, 0.94)",
        "warning_bg": "#3A2D1A",
        "warning_text": "#FDE7B2",
        "kicker": "#FDBA74",
        "chart_accent": "#FF9F43",
        "rolling": "#93C5FD",
        "series": ["#FF9F43", "#60A5FA", "#34D399", "#C084FC", "#F472B6", "#FACC15"],
        "quality": ["#34D399", "#FACC15", "#60A5FA", "#FF9F43", "#F87171"],
    },
}

BRAND = "#F08326"


def colors_for(theme: str) -> ThemeColors:
    """Return a defensive copy of the validated theme color tokens."""
    try:
        return dict(THEMES[theme])
    except KeyError as exc:
        raise ValueError(f"Unknown theme {theme!r}; expected one of {tuple(THEMES)}") from exc


def app_css(theme: str) -> str:
    """Create app styles using the same semantic tokens as the charts."""
    colors = colors_for(theme)
    return f"""
    :root {{
      color-scheme: {"dark" if theme == "Dark" else "light"};
      --primary-color: {BRAND};
      --background-color: {colors["background"]};
      --secondary-background-color: {colors["surface"]};
      --text-color: {colors["text"]};
      --brand-orange: {BRAND};
      --page-bg: {colors["background"]};
      --surface: {colors["surface"]};
      --surface-tint: {colors["surface_tint"]};
      --ink: {colors["text"]};
      --muted: {colors["muted"]};
      --border: {colors["border"]};
      --warning-bg: {colors["warning_bg"]};
      --warning-text: {colors["warning_text"]};
      --kicker: {colors["kicker"]};
    }}
    .stApp, [data-testid="stAppViewContainer"] {{
      background: var(--page-bg);
      color: var(--ink);
    }}
    [data-testid="stAppViewContainer"] > .main {{
      background: var(--page-bg);
    }}
    .block-container {{
      max-width: 1320px;
      padding-top: 4rem;
      padding-bottom: 2.5rem;
    }}
    [data-testid="stHeader"] {{ background: {colors["header"]}; }}
    [data-testid="stSidebar"] {{
      background: var(--surface);
      border-right: 1px solid var(--border);
    }}
    [data-testid="stSidebar"][aria-expanded="true"] {{
      min-width: 280px !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{
      background: var(--surface);
    }}
    [data-testid="stSidebar"] [data-testid="stSelectbox"] {{
      width: 100%;
    }}
    [data-testid="stSidebar"] [data-baseweb="select"] > div {{
      min-height: 42px;
      border-radius: 8px;
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
      border-color: var(--border) !important;
    }}
    [data-testid="stSidebar"] .st-key-player-selection-card {{
      background: var(--surface);
      border: 1px solid var(--border) !important;
      border-left: 4px solid var(--brand-orange) !important;
      border-radius: 12px;
      box-shadow: 0 4px 14px rgba(23, 33, 43, {"0.16" if theme == "Dark" else "0.055"});
    }}
    [data-testid="stSidebar"] [role="group"] {{
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: 8px;
      min-height: 42px;
    }}
    [data-testid="stSidebar"] [role="combobox"] {{
      color: var(--ink) !important;
    }}
    [data-testid="stSelectboxVirtualDropdown"] {{
      background: var(--surface) !important;
      border: 1px solid var(--border);
      border-radius: 10px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, {"0.38" if theme == "Dark" else "0.16"});
      color: var(--ink) !important;
      overflow: hidden;
    }}
    [data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {{
      background: var(--surface) !important;
      color: var(--ink) !important;
    }}
    [data-testid="stSelectboxVirtualDropdown"] [role="option"] {{
      color: var(--ink) !important;
    }}
    [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
    [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
    [data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused="true"] {{
      background: var(--surface-tint) !important;
      color: var(--ink) !important;
    }}
    [data-testid="stSelectboxVirtualDropdown"] [role="option"] * {{
      color: inherit !important;
    }}
    [data-testid="stSidebarCollapseButton"] button {{
      visibility: visible !important;
      color: var(--muted);
    }}
    [data-testid="stSidebarCollapseButton"] button:hover {{
      background: var(--surface-tint);
    }}
    [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] {{
      color: var(--muted) !important;
    }}
    [data-testid="stExpandSidebarButton"] button {{
      visibility: visible !important;
      color: var(--ink) !important;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
    }}
    [data-testid="stExpandSidebarButton"] button:hover {{
      background: var(--surface-tint);
    }}
    [data-testid="stExpandSidebarButton"] span,
    [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{
      color: var(--ink) !important;
    }}
    h1, h2, h3, h4, p, label, [data-testid="stMarkdownContainer"] {{
      color: var(--ink);
    }}
    h1, h2, h3 {{ letter-spacing: -0.025em; }}
    h1 {{ font-weight: 760; }}
    .brand-hero {{
      background: linear-gradient(110deg, var(--surface) 0%, var(--surface-tint) 100%);
      border: 1px solid var(--border);
      border-left: 5px solid var(--brand-orange);
      border-radius: 14px;
      padding: 18px 22px;
      margin: 0 0 12px;
    }}
    .brand-kicker {{
      color: var(--kicker);
      font-size: 0.72rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .brand-title {{
      color: var(--ink);
      font-size: clamp(1.75rem, 3.2vw, 2.45rem);
      font-weight: 760;
      line-height: 1.1;
      margin: 6px 0 5px;
    }}
    .brand-hero p {{ color: var(--muted); font-size: 0.95rem; margin: 0; }}
    [data-testid="stTabs"] {{
      border-bottom: 1px solid var(--border);
      margin: 4px 0 14px;
    }}
    [data-baseweb="tab"] {{
      min-height: 42px;
      padding: 10px 14px;
      color: var(--muted);
      font-weight: 700;
    }}
    [data-baseweb="tab"]:hover {{
      color: var(--ink);
      background: var(--surface-tint);
      border-radius: 8px 8px 0 0;
    }}
    [data-testid="stExpander"] {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin: 8px 0;
    }}
    [aria-selected="true"] {{
      color: var(--ink) !important;
    }}
    [data-testid="stMetric"] {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-top: 3px solid var(--brand-orange);
      border-radius: 12px;
      min-height: 112px;
      padding: 16px 18px;
      box-shadow: 0 4px 14px rgba(23, 33, 43, {"0.16" if theme == "Dark" else "0.055"});
    }}
    [data-testid="stMetricLabel"], [data-testid="stCaptionContainer"] {{
      color: var(--muted);
    }}
    [data-testid="stMetricValue"] {{
      color: var(--ink);
      font-weight: 760;
    }}
    [data-testid="stPlotlyChart"],
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      padding: 8px;
      box-shadow: 0 3px 12px rgba(23, 33, 43, {"0.16" if theme == "Dark" else "0.035"});
      overflow: hidden;
    }}
    [data-baseweb="tab-list"] {{ gap: 5px; }}
    [data-baseweb="tab"] {{ border-radius: 8px 8px 0 0; }}
    [aria-selected="true"] {{ border-bottom-color: var(--brand-orange) !important; }}
    div[data-testid="stAlert"] {{ border-radius: 10px; }}
    [data-testid="stAlert"][kind="warning"],
    [data-testid="stAlert"][kind="warning"] p {{
      background: var(--warning-bg);
      color: var(--warning-text);
      border-color: var(--brand-orange);
    }}
    div[data-baseweb="select"] > div, [data-baseweb="input"] > div {{
      background: var(--surface);
      border-color: var(--border);
      color: var(--ink);
    }}
    [data-baseweb="radio"] label {{
      color: var(--ink);
    }}
    [data-baseweb="radio"] [data-testid="stMarkdownContainer"] p {{
      color: var(--ink);
    }}
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input {{
      background: var(--surface);
      color: var(--ink);
      border-color: var(--border);
    }}
    [data-testid="stButton"] button {{
      border-color: var(--border);
      color: var(--ink);
    }}
    [data-testid="stButton"] button[kind="primary"] {{
      background: var(--brand-orange);
      border-color: var(--brand-orange);
      color: #FFFFFF;
    }}
    button[kind="secondary"] {{
      border-color: var(--border);
      color: var(--ink);
    }}
    """
