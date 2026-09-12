from __future__ import annotations

import base64
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

# Em hosts como o Streamlit Community Cloud, segredos ficam só em st.secrets,
# não em variáveis de ambiente — repassa para os.environ para o datajud_client usar.
if "DATAJUD_API_KEY" not in os.environ:
    try:
        if "DATAJUD_API_KEY" in st.secrets:
            os.environ["DATAJUD_API_KEY"] = st.secrets["DATAJUD_API_KEY"]
    except Exception:
        pass

from comunica_client import ComunicaClient, ComunicaError  # noqa: E402
from datajud_client import DataJudClient, DataJudError, NumeroProcessoCNJ  # noqa: E402


@st.cache_data
def _load_logo_data_uri(filename: str, _mtime: float) -> str:
    encoded = base64.b64encode((CODE_DIR / filename).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def load_logo_data_uri(filename: str) -> str:
    return _load_logo_data_uri(filename, (CODE_DIR / filename).stat().st_mtime)


st.set_page_config(page_title="GestorJus", page_icon="GJ", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root {
        --ink:#17232b; --muted:#6f7c80; --faint:#9aa6a1; --line:#e1e6e0; --line-strong:#cdd6cf;
        --paper:#f6f7f3; --surface:#ffffff; --teal:#147d72; --teal-dark:#0e5c54; --mint:#e5f2ec;
        --yellow:#efc96f; --coral:#e98770; --navy:#17262e; --navy-soft:#22343d;
        --shadow-sm: 0 1px 2px rgba(23,35,43,.05);
        --shadow-md: 0 6px 18px -8px rgba(23,35,43,.16);
        --radius: 10px;
    }
    html, body, [class*="css"] { font-family: Manrope, sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    #MainMenu, footer { visibility:hidden; }
    [data-testid="stHeader"] { background:transparent; height:0; min-height:0; overflow:visible; }
    [data-testid="stHeader"] *:not([data-testid="stExpandSidebarButton"]):not([data-testid="stExpandSidebarButton"] *):not(:has([data-testid="stExpandSidebarButton"])) { display:none; }
    [data-testid="stToolbar"] > *:not(:has([data-testid="stExpandSidebarButton"])) { display:none; }
    [data-testid="stDecoration"] { display:none; }
    [data-testid="stExpandSidebarButton"] {
        position:fixed !important; top:1rem; left:1rem; z-index:999;
    }
    .block-container { padding-top:1.4rem; }
    .block-container { max-width:1360px; padding:2rem 3.5rem 4rem; }

    /* Sidebar */
    [data-testid="stSidebar"] { background:linear-gradient(180deg,var(--sidebar-bg-start) 0%,var(--sidebar-bg-end) 100%); border-right:1px solid var(--sidebar-divider); }
    [data-testid="stSidebar"] * { color:var(--sidebar-text); }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.2rem; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"] {
        background-color:var(--surface) !important; border-color:var(--surface) !important; border-radius:8px;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] input {
        color:var(--ink) !important; background-color:transparent !important;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill:var(--ink) !important; }
    [data-testid="stSidebar"] .stButton { width:100%; }
    [data-testid="stSidebar"] .stButton > button {
        width:100%; background:var(--sidebar-btn-bg); border:none; border-radius:0; color:var(--sidebar-btn-text) !important;
        font-weight:600; justify-content:flex-start; text-align:left; padding:7px 14px; gap:.6rem;
        box-shadow:none; transition:background .15s ease;
    }
    [data-testid="stSidebar"] .stButton > button > div { justify-content:flex-start !important; }
    [data-testid="stSidebar"] .stButton > button p { text-align:left !important; }
    [data-testid="stSidebar"] .stButton > button:hover { background:var(--sidebar-btn-hover-bg); }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background:var(--sidebar-btn-selected-bg) !important; border:none !important; color:var(--sidebar-btn-selected-text) !important; box-shadow:none;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] p { color:var(--sidebar-btn-selected-text) !important; }
    [data-testid="stSidebar"] .stButton > button span[data-testid="stIconMaterial"],
    [data-testid="stSidebar"] .stButton > button span[role="img"] { color:var(--sidebar-btn-text) !important; }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] span[data-testid="stIconMaterial"],
    [data-testid="stSidebar"] .stButton > button[kind="primary"] span[role="img"] { color:var(--sidebar-btn-selected-text) !important; }
    [data-testid="stSidebar"] hr { width:100%; margin:0; border-color:var(--sidebar-divider); }
    [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(hr) {
        height:auto !important; margin:0; padding:.45rem 0;
    }
    [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small { color:var(--sidebar-text-muted) !important; letter-spacing:.4px; }

    /* Fixed-width sidebar: not resizable, but still collapsible */
    [data-testid="stSidebar"][aria-expanded="true"] {
        width:21rem !important; min-width:21rem !important; max-width:21rem !important;
    }
    [data-testid="stSidebar"] [style*="col-resize"] { display:none !important; pointer-events:none !important; }

    /* Center modal dialogs over the main content area, ignoring the sidebar's width */
    body:has([data-testid="stSidebar"][aria-expanded="true"]) div[data-testid="stDialog"] > div,
    body:has([data-testid="stSidebar"][aria-expanded="true"]) div[data-testid="stDialog"] div[role="dialog"] {
        transform: translateX(10.5rem);
    }

    /* Brand */
    .brand-title { color:var(--sidebar-title); font:800 16px Manrope; line-height:1.15; letter-spacing:-.2px; margin-top:2px; }
    .brand-subtitle { color:var(--sidebar-subtitle); font:10px 'DM Mono'; letter-spacing:1.2px; text-transform:uppercase; }
    div[class*="st-key-sidebar_brand"] { margin:.2rem 0 0 .1rem; }
    div[class*="st-key-sidebar_brand"] [data-testid="stHorizontalBlock"] { align-items:center; min-height:56px; height:auto !important; }
    div[class*="st-key-sidebar_brand"] [data-testid="stColumn"],
    div[class*="st-key-sidebar_brand"] [data-testid="stVerticalBlock"],
    div[class*="st-key-sidebar_brand"] [data-testid="stElementContainer"] { height:auto !important; min-height:56px; }
    .brand-logo-icon { width:60px; height:40px; min-width:60px; object-fit:contain; background:none; }

    /* Profile "carteirinha" card + logout on the Home screen */
    div[class*="st-key-home_profile_panel"] {
        position:fixed; bottom:2rem; right:3rem; width:280px; z-index:50;
        display:flex; flex-direction:column; gap:.9rem; height:auto !important;
    }
    div[class*="st-key-profile_id_card"] { position:relative; width:100%; }
    div[class*="st-key-profile_id_card"] .id-card {
        position:relative; display:flex; align-items:center; gap:.85rem;
        background:var(--surface); border:1px solid var(--line); border-radius:0;
        padding:.8rem .95rem; box-shadow:var(--shadow-md); cursor:pointer;
        transition:box-shadow .15s ease, transform .15s ease;
    }
    div[class*="st-key-profile_id_card"]:hover .id-card {
        box-shadow:0 10px 28px -10px rgba(23,35,43,.28); transform:translateY(-2px); border-color:var(--line-strong);
    }
    div[class*="st-key-profile_id_card"] .id-card-photo {
        width:52px; height:52px; min-width:52px; border-radius:0;
        background:linear-gradient(135deg,var(--yellow),#e0a94a); color:var(--navy) !important;
        display:flex; align-items:center; justify-content:center; font:800 17px Manrope;
    }
    div[class*="st-key-profile_id_card"] img.id-card-photo { background:var(--surface); object-fit:cover; }
    div[class*="st-key-profile_id_card"] .id-card-info { min-width:0; flex:1; }
    div[class*="st-key-profile_id_card"] .id-card-username {
        color:var(--ink) !important; font:800 15px Manrope; line-height:1.2;
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    div[class*="st-key-profile_id_card"] .id-card-office {
        color:var(--teal-dark) !important; font:700 11px Manrope; margin:.08rem 0 .3rem;
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    div[class*="st-key-profile_id_card"] .id-card-contact {
        color:var(--faint) !important; font:9.5px 'DM Mono'; line-height:1.5;
        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    }
    div[class*="st-key-profile_id_card"] [data-testid="stElementContainer"]:has([data-testid="stButton"]) {
        position:absolute !important; inset:0 !important; margin:0 !important; width:100% !important; height:100% !important;
    }
    div[class*="st-key-profile_id_card"] [data-testid="stButton"] {
        width:100% !important; height:100% !important; margin:0 !important;
    }
    div[class*="st-key-profile_id_card"] [data-testid="stButton"] > button {
        width:100% !important; height:100% !important; min-height:100% !important;
        opacity:0; cursor:pointer; padding:0; border:none; background:transparent; box-shadow:none;
    }
    div[class*="st-key-profile_id_card"] [data-testid="stMarkdown"] > div { display:block !important; height:auto !important; }
    div[class*="st-key-logout_button_wrap"] { width:100%; }
    div[class*="st-key-logout_button_wrap"] button {
        background:var(--surface); border:1px solid var(--line-strong); color:var(--muted) !important; font-weight:600;
    }
    div[class*="st-key-logout_button_wrap"] button:disabled { opacity:.7; cursor:not-allowed; }

    /* Typography helpers */
    .eyebrow { color:var(--teal); font:600 10.5px 'DM Mono'; letter-spacing:1.2px; text-transform:uppercase; }

    /* Hero */
    .hero { display:flex; justify-content:space-between; gap:2.5rem; align-items:flex-start; margin:.4rem 0 2.2rem; }
    .hero h1 { color:var(--ink); font:800 clamp(30px,3.6vw,46px) Manrope; letter-spacing:-1.6px; line-height:1.08; margin:.5rem 0 .7rem; }
    .lede { color:var(--muted); font:15px/1.65 Manrope; max-width:640px; }
    .source-list { color:var(--muted); font:13px Manrope; margin-top:.9rem; display:flex; align-items:center; gap:.6rem; }
    .source-list .eyebrow { color:var(--faint); }

    /* Welcome screen (no source selected) */
    @keyframes welcomeFadeIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
    .welcome-screen {
        min-height:calc(100vh - 8rem); display:flex; flex-direction:column; justify-content:center; align-items:flex-start;
    }
    .welcome-screen h1 {
        color:var(--ink); font:800 clamp(30px,3.6vw,46px) Manrope; letter-spacing:-1.6px; line-height:1.08; margin:0 0 .8rem;
        opacity:0; animation:welcomeFadeIn 1s ease .3s forwards;
    }
    .welcome-screen .lede {
        font-size:17px; max-width:520px;
        opacity:0; animation:welcomeFadeIn 1s ease 1.6s forwards;
    }

    /* Metric cards */
    .metric-card { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:1.1rem 1.25rem; min-height:104px; box-shadow:var(--shadow-sm); transition:box-shadow .15s ease, transform .15s ease; }
    .metric-card:hover { box-shadow:var(--shadow-md); transform:translateY(-1px); }
    .metric-card.green { background:var(--mint); border-color:#c9e5d7; }
    .metric-label { color:var(--faint); font:600 9.5px 'DM Mono'; letter-spacing:1px; }
    .metric-value { color:var(--ink); font:800 28px Manrope; margin:.5rem 0 0; letter-spacing:-.6px; }
    .metric-hint { color:var(--muted); font:11.5px Manrope; margin-top:.15rem; }

    /* Panels */
    .panel { background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:1.5rem 1.65rem; margin-top:1.2rem; box-shadow:var(--shadow-sm); }
    .panel-title { color:var(--ink); font:700 19px Manrope; letter-spacing:-.3px; margin:.4rem 0 1.1rem; }

    /* Flat table (background matches page, only horizontal lines) */
    .flat-table { width:100%; border-collapse:collapse; background:transparent; margin-top:0; }
    .flat-table th {
        text-align:left; color:var(--faint) !important; font:600 10px 'DM Mono'; letter-spacing:1px; text-transform:uppercase;
        padding:.55rem .5rem; border-bottom:1px solid var(--line-strong);
    }
    .flat-table td {
        text-align:left; color:var(--ink) !important; font:14px Manrope; padding:.7rem .5rem; border-bottom:1px solid var(--line);
    }
    .flat-table tr:last-child td { border-bottom:none; }

    /* Row-based table with an action button per row (Painel Geral / Cadastro) */
    .painel-row-th {
        color:var(--faint) !important; font:600 10px 'DM Mono'; letter-spacing:1px; text-transform:uppercase; padding:.3rem 0;
    }
    .painel-row-td { color:var(--ink) !important; font:14px Manrope; padding:.4rem 0; }
    [data-testid="stHorizontalBlock"]:has(.painel-row-td) { border-bottom:1px solid var(--line); align-items:center; min-height:2.4rem !important; }
    [data-testid="stHorizontalBlock"]:has(.painel-row-th) { border-bottom:1px solid var(--line-strong); align-items:center; min-height:1.7rem !important; }
    [data-testid="stVerticalBlock"]:has(> [data-testid="stHorizontalBlock"] .painel-row-th),
    [data-testid="stVerticalBlock"]:has(> [data-testid="stHorizontalBlock"] .painel-row-td) { gap:.1rem !important; }
    [data-testid="stMarkdown"]:has(.painel-row-th) > div,
    [data-testid="stMarkdown"]:has(.painel-row-td) > div { display:block !important; height:auto !important; }
    [data-testid="stMarkdown"]:has(.painel-row-th) [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdown"]:has(.painel-row-td) [data-testid="stMarkdownContainer"] { height:auto !important; }
    [data-testid="stElementContainer"]:has(.painel-row-th),
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .painel-row-th),
    [data-testid="stColumn"]:has(.painel-row-th) { height:auto !important; min-height:1.7rem !important; }
    [data-testid="stElementContainer"]:has(.painel-row-td),
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .painel-row-td),
    [data-testid="stColumn"]:has(.painel-row-td) { height:auto !important; min-height:2.4rem !important; }
    div[class*="st-key-painel_mov_"] button,
    div[class*="st-key-edit_processo_"] button,
    div[class*="st-key-edit_cnpj_"] button,
    div[class*="st-key-edit_sei_"] button,
    div[class*="st-key-sei_hist_"] button {
        width:30px; height:30px; padding:0; display:flex; align-items:center; justify-content:center;
        border-radius:6px; border:none; background:transparent; box-shadow:none;
    }
    div[class*="st-key-painel_mov_"] button:hover,
    div[class*="st-key-edit_processo_"] button:hover,
    div[class*="st-key-edit_cnpj_"] button:hover,
    div[class*="st-key-edit_sei_"] button:hover,
    div[class*="st-key-sei_hist_"] button:hover { background:var(--mint); }
    div[class*="st-key-painel_mov_"] button span[data-testid="stIconMaterial"],
    div[class*="st-key-edit_processo_"] button span[data-testid="stIconMaterial"],
    div[class*="st-key-edit_cnpj_"] button span[data-testid="stIconMaterial"],
    div[class*="st-key-edit_sei_"] button span[data-testid="stIconMaterial"],
    div[class*="st-key-sei_hist_"] button span[data-testid="stIconMaterial"] { color:var(--ink) !important; font-size:18px !important; }
    div[class*="st-key-sei_link_"] a[data-testid="stBaseLinkButton"] {
        width:30px; height:30px; padding:0; display:flex; align-items:center; justify-content:center;
        border-radius:6px; border:none; background:transparent; box-shadow:none;
    }
    div[class*="st-key-sei_link_"] a[data-testid="stBaseLinkButton"]:hover { background:var(--mint); }
    div[class*="st-key-sei_link_"] a[data-testid="stBaseLinkButton"] span[data-testid="stIconMaterial"] { color:var(--ink) !important; font-size:18px !important; }

    /* "leve-me até lá" link-style button inside movement dialogs */
    div[class*="st-key-mov_dialog_goto_wrap"] { margin-top:.6rem; }
    div[class*="st-key-mov_dialog_goto"] button {
        background:transparent; border:none; box-shadow:none; padding:0;
        color:var(--teal-dark) !important; font-weight:700; justify-content:flex-end;
    }
    div[class*="st-key-mov_dialog_goto"] button:hover { text-decoration:underline; }
    div[class*="st-key-mov_dialog_goto"] button p { text-align:right !important; }

    /* Small toolbar buttons (filter / add / delete): compact, flat, no border, top-left above table */
    div[class*="_toolbar"][data-testid="stVerticalBlock"] {
        flex-direction:row !important; align-items:center !important; gap:.15rem !important; margin-top:.2rem; margin-bottom:0;
    }
    div[data-testid="stLayoutWrapper"]:has(> [class*="_toolbar"]) { margin-bottom:-1rem !important; }
    div[class*="_toolbar"][data-testid="stVerticalBlock"] [data-testid="stElementContainer"] { width:fit-content !important; }
    div[class*="st-key-toolbar_"] [data-testid="stTooltipHoverTarget"] { width:auto !important; }
    div[class*="st-key-toolbar_"] button {
        width:30px; height:30px; padding:0; display:flex; align-items:center; justify-content:center;
        border-radius:6px; border:none; background:var(--paper); box-shadow:none;
    }
    div[class*="st-key-toolbar_"] button:hover { background:var(--mint); }
    div[class*="st-key-toolbar_"] button p { margin:0 !important; font:16px Manrope !important; }
    div[class*="st-key-toolbar_"] button span[data-testid="stIconMaterial"] { color:var(--ink) !important; font-size:18px !important; }

    /* Período preset buttons (Hoje / Ontem / 1M / 3M / 6M / 1A / Todos): small pills */
    div[class*="_periodo_buttons"] [data-testid="stHorizontalBlock"] { gap:.3rem !important; }
    div[class*="_periodo_buttons"] button {
        padding:.2rem .4rem; min-height:0; height:26px; font-size:11px; border-radius:6px;
    }
    div[class*="_periodo_buttons"] button p { font-size:11px !important; margin:0 !important; }


    /* Status chips */
    .status-ok, .status-warn, .status-neutral { border-radius:8px; padding:.8rem 1.05rem; font:500 12.5px/1.5 Manrope; margin:.3rem 0; }
    .status-ok { color:var(--teal-dark); background:var(--mint); border:1px solid #c9e5d7; }
    .status-warn { color:#8a6d1f; background:#fdf6e3; border:1px solid #f1e0ad; border-left:3px solid var(--yellow); }
    .status-neutral { color:var(--muted); background:#f1f3ef; border:1px solid var(--line); }
    .process-code { color:var(--teal-dark); font:500 12px 'DM Mono'; background:var(--mint); border-radius:6px; padding:.45rem .7rem; margin:.3rem 0; }

    /* Streamlit widget polish */
    .stButton > button, .stFormSubmitButton > button, .stLinkButton > a { border-radius:8px; font-weight:700; letter-spacing:-.1px; transition:transform .1s ease, box-shadow .15s ease; }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"], .stLinkButton > a[kind="primary"] {
        background:var(--btn-primary); border:1px solid var(--btn-primary); color:var(--on-btn-primary) !important;
        box-shadow:0 4px 12px -4px rgba(20,125,114,.3);
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover, .stLinkButton > a[kind="primary"]:hover {
        background:var(--btn-primary-dark); border-color:var(--btn-primary-dark); color:var(--on-btn-primary) !important; transform:translateY(-1px);
    }
    .stButton > button[kind="primary"] p, .stFormSubmitButton > button[kind="primaryFormSubmit"] p, .stLinkButton > a[kind="primary"] p { color:var(--on-btn-primary) !important; }
    .stButton > button:not([kind="primary"]) { border-color:var(--line-strong); }
    .stFormSubmitButton > button:not([kind="primaryFormSubmit"]) { border-color:var(--line-strong); }
    .stLinkButton > a[disabled], .stLinkButton > a[aria-disabled="true"] {
        background:var(--btn-primary); border-color:var(--btn-primary); color:var(--on-btn-primary) !important; opacity:.5; pointer-events:none;
    }
    div[data-testid="stForm"] { border:1px dashed var(--line-strong); border-radius:8px; padding:1.1rem 1.1rem .3rem; background:#fbfcfa; }
    .stTextInput input, .stSelectbox [data-baseweb="select"] { border-radius:7px !important; }
    .stTextInput input:focus { border-color:var(--teal) !important; box-shadow:0 0 0 1px var(--teal) !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid var(--line); }
    .stTabs [data-baseweb="tab"] { height:44px; border-radius:8px 8px 0 0; padding:0 18px; font-weight:700; color:var(--muted); background:transparent; }
    .stTabs [aria-selected="true"] { color:var(--teal-dark) !important; background:var(--mint); }
    .stTabs [data-baseweb="tab-highlight"] { background-color:var(--teal); }
    .stTabs [data-baseweb="tab-border"] { display:none; }

    /* Square link button (SEI access link) */
    div[class*="st-key-sei_dialog_link_"] a[data-testid="stBaseLinkButton"] {
        display:flex; align-items:center; justify-content:center;
        width:48px; height:48px; padding:0; font-size:18px; border-radius:8px;
    }


    /* Expander & dataframe */
    div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:8px; background:var(--surface); }
    div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:8px; overflow:hidden; }

    h2,h3,p { font-family:Manrope,sans-serif; }
    @media (max-width:900px) { .block-container { padding:1.5rem 1.5rem 3rem; } .hero { display:block; } }
    </style>
    """,
    unsafe_allow_html=True,
)


COLOR_PALETTES = {
    "Teal & Ouro": {
        "ink": "#000000", "muted": "#4a4a4a", "faint": "#8a8a8a",
        "line": "#e2e2e2", "line-strong": "#cccccc",
        "paper": "#f7f7f5", "surface": "#ffffff",
        "teal": "#3D9B9A", "teal-dark": "#143A3B", "mint": "#e3f1f0",
        "yellow": "#D59B1D", "coral": "#e98770",
        "navy": "#143A3B", "navy-soft": "#1c4d4e",
        "btn-primary": "#3D9B9A", "btn-primary-dark": "#143A3B", "on-btn-primary": "#ffffff",
        "sidebar-bg-start": "#143A3B", "sidebar-bg-end": "#1c4d4e",
        "sidebar-text": "#d9e9df", "sidebar-text-muted": "#7f9990",
        "sidebar-title": "#ffffff", "sidebar-subtitle": "#8fac9f",
        "sidebar-border": "rgba(255,255,255,.14)", "sidebar-border-strong": "rgba(255,255,255,.22)",
        "sidebar-hover": "rgba(255,255,255,.07)", "sidebar-divider": "rgba(255,255,255,.12)",
        "sidebar-btn-bg": "transparent", "sidebar-btn-hover-bg": "rgba(255,255,255,.07)",
        "sidebar-btn-border": "rgba(255,255,255,.14)", "sidebar-btn-text": "#d9e9df",
        "sidebar-btn-selected-bg": "#0c2323", "sidebar-btn-selected-text": "#ffffff",
        "app-logo": "logo_white.png",
    },
    "ZERO": {
        "ink": "#000000", "muted": "#545b6c", "faint": "#8990a1",
        "line": "#e3e3e1", "line-strong": "#cfcfcd",
        "paper": "#f7f6f2", "surface": "#ffffff",
        "teal": "#12264A", "teal-dark": "#0c1a33", "mint": "#eef1f6",
        "yellow": "#FFC400", "coral": "#e98770",
        "navy": "#12264A", "navy-soft": "#1c355e",
        "btn-primary": "#FFC400", "btn-primary-dark": "#E6B000", "on-btn-primary": "#000000",
        "sidebar-bg-start": "#ffffff", "sidebar-bg-end": "#ffffff",
        "sidebar-text": "#000000", "sidebar-text-muted": "rgba(0,0,0,.6)",
        "sidebar-title": "#000000", "sidebar-subtitle": "rgba(0,0,0,.65)",
        "sidebar-border": "rgba(0,0,0,.12)", "sidebar-border-strong": "rgba(18,38,74,.4)",
        "sidebar-hover": "rgba(18,38,74,.06)", "sidebar-divider": "rgba(0,0,0,.1)",
        "sidebar-btn-bg": "transparent", "sidebar-btn-hover-bg": "rgba(18,38,74,.06)",
        "sidebar-btn-border": "#12264A", "sidebar-btn-text": "#12264A",
        "sidebar-btn-selected-bg": "#12264A", "sidebar-btn-selected-text": "#ffffff",
        "app-logo": "logo.png",
    },
}

if "color_palette" not in st.session_state:
    st.session_state.color_palette = "Teal & Ouro"

_active_palette = COLOR_PALETTES[st.session_state.color_palette]
st.markdown(
    "<style>:root {"
    + "".join(f"--{var}:{value};" for var, value in _active_palette.items())
    + "}</style>",
    unsafe_allow_html=True,
)


def card(label: str, value: str, hint: str, green: bool = False) -> None:
    tone = " green" if green else ""
    st.markdown(
        f'<div class="metric-card{tone}"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-hint">{hint}</div></div>',
        unsafe_allow_html=True,
    )


def status(message: str, kind: str = "neutral") -> None:
    st.markdown(f'<div class="status-{kind}">{message}</div>', unsafe_allow_html=True)


@st.dialog("Processos cadastrados")
def show_processes_dialog() -> None:
    if not st.session_state.processes:
        status("Nenhum processo cadastrado ainda.")
    else:
        st.dataframe(
            [
                {"Nome de referência": item["label"], "Número CNJ": item["number"]}
                for item in st.session_state.processes
            ],
            use_container_width=True,
            hide_index=True,
        )


@st.dialog("CNPJs cadastrados")
def show_cnpjs_dialog() -> None:
    if not st.session_state.monitored_cnpjs:
        status("Nenhum CNPJ cadastrado ainda.")
    else:
        st.dataframe(
            [
                {"Nome da empresa / Razão Social": item["label"], "CNPJ": format_cnpj_br(item["cnpj"])}
                for item in st.session_state.monitored_cnpjs
            ],
            use_container_width=True,
            hide_index=True,
        )


def find_credencial_for_processo(numero: str):
    for item in st.session_state.credenciais:
        if item.get("processo") == numero:
            return item
    return None


def credencial_status(validade):
    if not validade:
        return ("Sem prazo de validade informado", "neutral")
    dias = (validade - date.today()).days
    if dias < 0:
        return (f"Vencido há {abs(dias)} dia(s)", "warn")
    if dias <= 15:
        return (f"Vence em {dias} dia(s)", "warn")
    return (f"Válido até {validade.strftime('%d/%m/%Y')}", "ok")


SEI_LINK_STATUS_CATEGORIES = ["Ativo", "Em vencimento", "Vencido"]


def sei_link_status(proc) -> tuple[str, str | None]:
    """Retorna (rótulo exibido, categoria) para o status do link de acesso do processo SEI.

    Categoria é uma de SEI_LINK_STATUS_CATEGORIES, ou None quando não se aplica
    (consulta pública ou link não cadastrado)."""
    if proc.get("forma_acesso") != "Link de acesso":
        return "Consulta pública", None
    credencial = find_credencial_for_processo(proc["number"])
    if not credencial or not credencial.get("link"):
        return "Link não cadastrado", None
    validade = credencial.get("validade")
    if not validade:
        return "Ativo (sem prazo informado)", "Ativo"
    dias = (validade - date.today()).days
    if dias < 0:
        return f"Vencido há {abs(dias)} dia(s)", "Vencido"
    if dias <= 10:
        return f"Vence em {dias} dia(s)", "Em vencimento"
    return f"Válido até {validade.strftime('%d/%m/%Y')}", "Ativo"


@st.dialog("Cadastrar link de acesso")
def show_add_credencial_dialog() -> None:
    sei_process_options = ["(nenhum processo vinculado)"] + [p["number"] for p in st.session_state.sei_processes]
    with st.form("credencial_form", clear_on_submit=True):
        cred_org = st.selectbox("Órgão", SEI_ORGAOS + ["Outro"], key="cred_org")
        cred_processo = st.selectbox("Processo vinculado", sei_process_options, key="cred_processo")
        cred_link = st.text_input("Link de acesso", placeholder="https://sei.orgao.gov.br/... (ainda não disponível)", key="cred_link")
        cred_validade = st.date_input("Prazo de validade", value=None, key="cred_validade")
        cred_add = st.form_submit_button("Cadastrar credencial", use_container_width=True)
    if cred_add:
        if not cred_link.strip():
            st.warning("Informe o link de acesso.")
        else:
            st.session_state.credenciais.append({
                "org": cred_org,
                "processo": None if cred_processo == "(nenhum processo vinculado)" else cred_processo,
                "link": cred_link.strip(),
                "validade": cred_validade,
            })
            st.success("Credencial cadastrada.")
            st.rerun()


@st.dialog("Editar link de acesso")
def show_edit_credencial_dialog(index: int) -> None:
    item = st.session_state.credenciais[index]
    sei_process_options = ["(nenhum processo vinculado)"] + [p["number"] for p in st.session_state.sei_processes]
    org_options = SEI_ORGAOS + ["Outro"]
    current_org = item.get("org")
    org_index = org_options.index(current_org) if current_org in org_options else len(org_options) - 1
    current_processo = item.get("processo") or "(nenhum processo vinculado)"
    processo_index = sei_process_options.index(current_processo) if current_processo in sei_process_options else 0

    with st.form("credencial_edit_form"):
        cred_org = st.selectbox("Órgão", org_options, index=org_index, key="cred_edit_org")
        cred_processo = st.selectbox("Processo vinculado", sei_process_options, index=processo_index, key="cred_edit_processo")
        cred_link = st.text_input("Link de acesso", value=item.get("link") or "", key="cred_edit_link")
        cred_validade = st.date_input("Prazo de validade", value=item.get("validade"), key="cred_edit_validade")
        save_col, remove_col = st.columns(2)
        with save_col:
            cred_save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            cred_remove = st.form_submit_button("Remover credencial", use_container_width=True)

    if cred_save:
        if not cred_link.strip():
            st.warning("Informe o link de acesso.")
        else:
            st.session_state.credenciais[index] = {
                "org": cred_org,
                "processo": None if cred_processo == "(nenhum processo vinculado)" else cred_processo,
                "link": cred_link.strip(),
                "validade": cred_validade,
            }
            st.success("Credencial atualizada.")
            st.rerun()
    if cred_remove:
        st.session_state.credenciais.pop(index)
        st.success("Credencial removida.")
        st.rerun()


@st.dialog("Filtrar credenciais")
def show_cred_filter_dialog() -> None:
    filters = st.session_state.setdefault("cred_filters", {"orgaos": []})
    orgao_options = sorted({item["org"] for item in st.session_state.credenciais})
    selected_orgaos = st.multiselect(
        "Órgão", orgao_options, default=[o for o in filters["orgaos"] if o in orgao_options], key="cred_filter_orgaos_input"
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="cred_filter_apply", type="primary", use_container_width=True):
            st.session_state.cred_filters = {"orgaos": selected_orgaos}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="cred_filter_clear", use_container_width=True):
            st.session_state.cred_filters = {"orgaos": []}
            st.rerun()


def render_sei_process_panel(processo: dict) -> None:
    st.markdown(
        f"**Processo:** {processo['number']}  \n"
        f"**Interessado:** {processo.get('interessado') or 'não informado'} · "
        f"**Responsável:** {processo.get('responsavel') or 'não informado'}  \n"
        f"**Órgão:** {processo['org']} · **Tipo:** {processo.get('tipo', 'não informado')}"
    )
    last_query = processo.get("last_query")
    status(f"Última consulta: {last_query.strftime('%d/%m/%Y %H:%M') if last_query else 'nunca consultado'}")

    if processo.get("forma_acesso") == "Link de acesso":
        credencial = find_credencial_for_processo(processo["number"])
        link_col, status_col = st.columns([1, 3])
        with link_col:
            with st.container(key=f"sei_dialog_link_{processo['number']}"):
                st.link_button("↗", credencial["link"] if credencial and credencial.get("link") else "#", disabled=not (credencial and credencial.get("link")))
        with status_col:
            if credencial and credencial.get("link"):
                label, kind = credencial_status(credencial.get("validade"))
                status(f"Link cadastrado em Links e Autenticações · {label}", kind)
            else:
                status("Link ainda não cadastrado.", "warn")
        st.caption("O botão abre o SEI para captura manual das movimentações mais recentes.")

    st.markdown('<div class="eyebrow">HISTÓRICO DE MOVIMENTAÇÕES</div>', unsafe_allow_html=True)
    if processo.get("movements"):
        st.dataframe(
            [
                {"Data": mov.get("data"), "Unidade": mov.get("unidade"), "Descrição": mov.get("descricao")}
                for mov in processo["movements"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
        )
    else:
        status("Nenhuma movimentação capturada ainda para este processo.")


DJEN_COUNT_CAP = 10000


def format_djen_count(count) -> str:
    if count == DJEN_COUNT_CAP:
        return "10000+ (limite da API)"
    return str(count)


def format_cnpj_br(digits: str) -> str:
    if len(digits) != 14:
        return digits
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def resolve_orgao_label(numero: str) -> str:
    try:
        parsed = NumeroProcessoCNJ.parse(numero)
    except ValueError:
        return "—"
    alias = parsed.resolver_alias_datajud()
    if alias:
        return alias.removeprefix("api_publica_").upper()
    return parsed.segmento_nome


DATE_INPUT_FORMATS = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y%m%d%H%M%S")


def parse_date_value(value):
    """Converte datas das APIs para date real, para ordenação correta em tabelas."""
    if not value:
        return None
    text = str(value)
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def filter_rows_by_date_range(rows: list, date_start, date_end) -> list:
    if not date_start and not date_end:
        return rows
    filtered = rows
    if date_start:
        filtered = [row for row in filtered if row.get("Data") and row["Data"] >= date_start]
    if date_end:
        filtered = [row for row in filtered if row.get("Data") and row["Data"] <= date_end]
    return filtered


PERIODO_PRESETS = ["Hoje", "Ontem", "1M", "3M", "6M", "1A", "Todos"]


def _periodo_preset_range(preset: str):
    today = date.today()
    if preset == "Hoje":
        return today, today
    if preset == "Ontem":
        ontem = today - timedelta(days=1)
        return ontem, ontem
    if preset == "1M":
        return today - timedelta(days=30), today
    if preset == "3M":
        return today - timedelta(days=90), today
    if preset == "6M":
        return today - timedelta(days=180), today
    if preset == "1A":
        return today - timedelta(days=365), today
    return None, None


def render_periodo_selector_row(key_prefix: str, periodo_col):
    """Renders the período preset buttons aligned with a sibling column (e.g. the processo/CNPJ selector)."""
    state_key = f"{key_prefix}_periodo_preset"
    st.session_state.setdefault(state_key, "Todos")
    with periodo_col:
        st.markdown('<div class="eyebrow">Selecionar período de consulta:</div>', unsafe_allow_html=True)
        with st.container(key=f"{key_prefix}_periodo_buttons"):
            preset_cols = st.columns(len(PERIODO_PRESETS))
            for preset_col, preset in zip(preset_cols, PERIODO_PRESETS):
                with preset_col:
                    is_active = st.session_state[state_key] == preset
                    if st.button(
                        preset,
                        key=f"{key_prefix}_preset_{preset}",
                        type="primary" if is_active else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state[state_key] = preset
                        st.rerun()
    return _periodo_preset_range(st.session_state[state_key])


def format_date_br(value):
    parsed = parse_date_value(value)
    return parsed.strftime("%d/%m/%Y") if parsed else value


def _render_movimentacoes_rows(rows: list[dict]) -> None:
    if not rows:
        status("Nenhuma movimentação registrada ainda. Consulte este item em Monitoramento para capturar dados.", "warn")
        return
    rows_sorted = sorted(rows, key=lambda r: r.get("Data") or date.min, reverse=True)
    column_config = {"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")}
    if "Origem" in rows_sorted[0]:
        column_config["Origem"] = st.column_config.LinkColumn("Origem", display_text="Abrir ↗")
    st.dataframe(rows_sorted, use_container_width=True, hide_index=True, column_config=column_config)


@st.dialog("Últimas movimentações", width="large")
def show_movimentacoes_dialog(
    titulo: str,
    rows: list[dict] | None = None,
    nav_state: dict | None = None,
    ultima_atualizacao=None,
    consultar_link: str | None = None,
    consultar_proc: dict | None = None,
    consultar_action=None,
    refresh=None,
    sources: dict[str, list[dict]] | None = None,
    default_source: str | None = None,
    unavailable_sources: dict[str, str] | None = None,
) -> None:
    st.markdown(f'<div class="eyebrow">{html.escape(titulo)}</div>', unsafe_allow_html=True)

    if consultar_action is not None:
        if st.button("Consultar", type="primary", use_container_width=True, key="mov_dialog_consultar_action"):
            with st.spinner("Consultando..."):
                consultar_action()
    elif consultar_proc is not None:
        st.link_button(
            "Consultar",
            consultar_link or "#",
            type="primary",
            use_container_width=True,
            disabled=not consultar_link,
            on_click=lambda proc=consultar_proc: proc.__setitem__("last_query", datetime.now()),
            key="mov_dialog_consultar",
        )
        if not consultar_link:
            status("Link de acesso não cadastrado para este processo.", "warn")

    if refresh is not None:
        refreshed = refresh()
        rows = refreshed.get("rows", rows)
        sources = refreshed.get("sources", sources)
        ultima_atualizacao = refreshed.get("ultima_atualizacao", ultima_atualizacao)

    if ultima_atualizacao is not None:
        st.caption(f"Última atualização: {ultima_atualizacao.strftime('%d/%m/%Y %H:%M')}")
    else:
        st.caption("Última atualização: nunca consultado")

    if sources is not None:
        source_labels = list(sources.keys())
        default = default_source if default_source in source_labels else source_labels[0]
        chosen_source = st.segmented_control(
            "Fonte", source_labels, default=default, key="mov_dialog_fonte", label_visibility="collapsed"
        ) or default
        if unavailable_sources and chosen_source in unavailable_sources:
            status(unavailable_sources[chosen_source])
        else:
            _render_movimentacoes_rows(sources.get(chosen_source, []))
    else:
        _render_movimentacoes_rows(rows or [])

    if nav_state:
        with st.container(key="mov_dialog_goto_wrap"):
            goto_col = st.columns([3, 2])[1]
            with goto_col:
                if st.button("leve-me até lá  →", key="mov_dialog_goto", use_container_width=True):
                    for state_key, state_value in nav_state.items():
                        st.session_state[state_key] = state_value
                    st.session_state.active_module = "Monitoramento"
                    st.rerun()


def dje_datajud_rows(numero: str) -> list[dict]:
    datajud_result = st.session_state.datajud_results.get(numero)
    if not datajud_result:
        return []
    return [
        {
            "Data": parse_date_value(item.get("data_hora")),
            "Unidade": item.get("bruto", {}).get("orgaoJulgador", {}).get("nome") or "não informado",
            "Descrição": item.get("nome") or "não informada",
        }
        for item in datajud_result["movements"]
    ]


def dje_djen_rows(numero: str) -> list[dict]:
    djen_response = st.session_state.djen_results.get(numero)
    if not djen_response:
        return []
    return [
        {
            "Data": parse_date_value(item.get("data_disponibilizacao")),
            "Unidade/Órgão": item.get("nomeOrgao") or "não informado",
            "Descrição": item.get("tipoComunicacao") or item.get("tipoDocumento") or "Publicação",
            "Origem": item.get("link"),
        }
        for item in djen_response.get("items", [])
    ]


def movimentacoes_sei_processo(processo: dict) -> list[dict]:
    return [
        {"Data": parse_date_value(m.get("data")), "Unidade": m.get("unidade"), "Descrição": m.get("descricao")}
        for m in processo.get("movements", [])
    ]


def ultima_movimentacao_sei(processo: dict):
    movimentos = movimentacoes_sei_processo(processo)
    if not movimentos:
        return None, None
    ultima = max(movimentos, key=lambda m: m.get("Data") or date.min)
    return ultima.get("Data"), ultima.get("Descrição")


def movimentacoes_cnpj(cnpj_key: str) -> list[dict]:
    djen_response = st.session_state.djen_cnpj_results.get(cnpj_key)
    if not djen_response:
        return []
    return [
        {
            "Data": parse_date_value(i.get("data_disponibilizacao")),
            "Processo": i.get("numeroprocessocommascara") or i.get("numero_processo"),
            "Unidade/Órgão": i.get("nomeOrgao") or "não informado",
            "Descrição": i.get("tipoComunicacao") or i.get("tipoDocumento") or "Publicação",
            "Origem": i.get("link"),
        }
        for i in djen_response.get("items", [])
    ]


def consultar_dje_processo(process_number: str) -> None:
    try:
        parsed = NumeroProcessoCNJ.parse(process_number)
    except ValueError:
        parsed = None
    if not parsed:
        st.error("Informe um número CNJ válido.")
        return
    try:
        response = ComunicaClient().buscar_todos(numero_processo=process_number)
        st.session_state.djen_results[process_number] = response
    except ComunicaError as exc:
        st.error(f"DJEN: {exc}")
    try:
        client = DataJudClient()
        response = client.buscar_por_numero_processo(parsed)
        hits = response.get("hits", {}).get("hits", [])
        source = hits[0].get("_source", {}) if hits else {}
        movements = client.extrair_movimentacoes(response)
        st.session_state.datajud_results[process_number] = {
            "response": response, "source": source, "movements": movements,
        }
    except DataJudError as exc:
        st.error(f"DataJud: {exc}")
    st.session_state.query_timestamps[process_number] = datetime.now()


DJE_CNPJ_NOT_IMPLEMENTED_MSG = (
    "A API própria do DJe ainda não tem integração implementada, então não é possível "
    "exibir uma tabela de movimentações por processo aqui. Use a aba \"Diário (DJEN)\" "
    "para ver as publicações já disponíveis, ou consulte cada processo individualmente "
    "na aba Processos."
)


def consultar_dje_cnpj(cnpj_item: dict) -> None:
    cnpj_key = cnpj_item["cnpj"]
    try:
        response = ComunicaClient().buscar_todos(nome_parte=cnpj_item["label"])
        st.session_state.djen_cnpj_results[cnpj_key] = response
        st.session_state.cnpj_query_timestamps[cnpj_key] = datetime.now()
    except ComunicaError as exc:
        st.error(f"DJEN: {exc}")


if "processes" not in st.session_state:
    st.session_state.processes = [
        {"number": "0001149-33.2026.8.26.0127", "label": "TJSP · exemplo real", "responsavel": ""},
        {"number": "5000145-27.2016.8.13.0016", "label": "TJMG · exemplo real", "responsavel": ""},
        {"number": "0802205-61.2024.8.19.0021", "label": "TJRJ · exemplo real", "responsavel": ""},
        {"number": "1031108-73.2025.4.01.3400", "label": "TRF1 · exemplo real", "responsavel": ""},
    ]
if "monitored_cnpjs" not in st.session_state:
    st.session_state.monitored_cnpjs = [
        {"cnpj": "01652106000132", "label": "Express Brasília Hospedagem e Turismo S/A", "cliente": "", "responsavel": ""},
        {"cnpj": "05217384000151", "label": "H Plus Administração e Hotelaria Ltda", "cliente": "", "responsavel": ""},
    ]
if "djen_results" not in st.session_state:
    st.session_state.djen_results = {}
if "datajud_results" not in st.session_state:
    st.session_state.datajud_results = {}
if "query_timestamps" not in st.session_state:
    st.session_state.query_timestamps = {}
if "djen_cnpj_results" not in st.session_state:
    st.session_state.djen_cnpj_results = {}
if "cnpj_query_timestamps" not in st.session_state:
    st.session_state.cnpj_query_timestamps = {}
if "sei_processes" not in st.session_state:
    st.session_state.sei_processes = [
        {
            "number": "04001-00006993/2025-40",
            "org": "Governo do Distrito Federal",
            "interessado": "",
            "responsavel": "",
            "sistema_origem": "SEI",
            "tipo": "Outro",
            "forma_acesso": "Link de acesso",
            "movements": [],
            "last_query": None,
        },
    ]
if "credenciais" not in st.session_state:
    st.session_state.credenciais = [
        {
            "org": "Governo do Distrito Federal",
            "processo": "04001-00006993/2025-40",
            "link": "http://sei.df.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=2442842&infra_hash=f930b708871a3a2490e540fef130a96a",
            "validade": date(2026, 9, 4),
        },
    ]

SEI_ORGAOS = ["Ministério do Esporte", "Governo do Distrito Federal"]
SEI_TIPOS = ["Sancionador", "Prestação de contas", "Convênio", "Outro"]
SEI_FORMAS_ACESSO = ["Link de acesso", "Consulta pública"]


@st.dialog("Cadastrar processo")
def show_add_process_dialog() -> None:
    with st.form("process_form", clear_on_submit=True):
        new_process_label = st.text_input("Nome de referência", placeholder="Ex.: Ação principal · cliente")
        new_process_number = st.text_input("Número CNJ", value="", placeholder="0000000-00.0000.0.00.0000")
        new_process_responsavel = st.text_input("Responsável", placeholder="Ex.: Advogado(a) responsável")
        add_process = st.form_submit_button("Adicionar à lista", use_container_width=True)
    if add_process:
        try:
            normalized = NumeroProcessoCNJ.parse(new_process_number.strip()).bruto
            if any(item["number"] == normalized for item in st.session_state.processes):
                st.warning("Esse processo já está na lista.")
            else:
                st.session_state.processes.append({
                    "number": normalized,
                    "label": new_process_label.strip() or "Processo monitorado",
                    "responsavel": new_process_responsavel.strip(),
                })
                st.session_state.process_number = normalized
                st.success("Processo adicionado à lista.")
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    with st.expander("Importar lista de processos (um número CNJ por linha)"):
        bulk_process_text = st.text_area(
            "Números CNJ",
            placeholder="0000000-00.0000.0.00.0000\n0000001-11.2020.8.26.0100",
            height=120,
            key="bulk_process_text",
        )
        if st.button("Importar lista", key="bulk_process_import", use_container_width=True):
            lines = [line.strip() for line in bulk_process_text.splitlines() if line.strip()]
            added, duplicated, invalid = 0, 0, []
            for line in lines:
                try:
                    normalized = NumeroProcessoCNJ.parse(line).bruto
                except ValueError:
                    invalid.append(line)
                    continue
                if any(item["number"] == normalized for item in st.session_state.processes):
                    duplicated += 1
                    continue
                st.session_state.processes.append({"number": normalized, "label": "Processo importado", "responsavel": ""})
                added += 1
            if added:
                st.success(f"{added} processo(s) importado(s).")
            if duplicated:
                st.warning(f"{duplicated} número(s) já estavam na lista.")
            if invalid:
                st.error("Linhas inválidas: " + "; ".join(invalid))
            if added:
                st.rerun()


@st.dialog("Cadastrar CNPJ")
def show_add_cnpj_dialog() -> None:
    with st.form("cnpj_form", clear_on_submit=True):
        cnpj = st.text_input("CNPJ", placeholder="00.000.000/0000-00")
        cnpj_label = st.text_input("Nome da empresa / Razão Social", placeholder="Empresa monitorada")
        cnpj_cliente = st.text_input("Nome do Cliente", placeholder="Ex.: Cliente responsável por este CNPJ")
        add_cnpj = st.form_submit_button("Adicionar CNPJ", use_container_width=True)
    if add_cnpj:
        digits = "".join(char for char in cnpj if char.isdigit())
        if len(digits) != 14 or not cnpj_label.strip():
            st.warning("Informe um CNPJ válido e o nome da empresa.")
        elif any(item["cnpj"] == digits for item in st.session_state.monitored_cnpjs):
            st.warning("Esse CNPJ já está monitorado.")
        else:
            st.session_state.monitored_cnpjs.append(
                {"cnpj": digits, "label": cnpj_label.strip(), "cliente": cnpj_cliente.strip()}
            )
            st.success("CNPJ adicionado ao monitoramento.")
            st.rerun()

    with st.expander("Importar lista de CNPJs (um por linha, formato CNPJ;Nome opcional)"):
        bulk_cnpj_text = st.text_area(
            "CNPJs",
            placeholder="00.000.000/0000-00;Empresa A\n11.111.111/0001-11;Empresa B",
            height=120,
            key="bulk_cnpj_text",
        )
        if st.button("Importar lista", key="bulk_cnpj_import", use_container_width=True):
            lines = [line.strip() for line in bulk_cnpj_text.splitlines() if line.strip()]
            added, duplicated, invalid = 0, 0, []
            for line in lines:
                parts = re.split(r"[;,\t]", line, maxsplit=1)
                raw_cnpj = parts[0]
                raw_label = parts[1].strip() if len(parts) > 1 else ""
                digits = "".join(char for char in raw_cnpj if char.isdigit())
                if len(digits) != 14:
                    invalid.append(line)
                    continue
                if any(item["cnpj"] == digits for item in st.session_state.monitored_cnpjs):
                    duplicated += 1
                    continue
                st.session_state.monitored_cnpjs.append(
                    {"cnpj": digits, "label": raw_label or "Empresa importada", "cliente": "", "responsavel": ""}
                )
                added += 1
            if added:
                st.success(f"{added} CNPJ(s) importado(s).")
            if duplicated:
                st.warning(f"{duplicated} CNPJ(s) já estavam na lista.")
            if invalid:
                st.error("Linhas inválidas: " + "; ".join(invalid))
            if added:
                st.rerun()


@st.dialog("Editar processo")
def show_edit_process_dialog(index: int) -> None:
    item = st.session_state.processes[index]
    with st.form("process_edit_form"):
        edit_label = st.text_input("Nome de referência", value=item["label"])
        edit_number = st.text_input("Número CNJ", value=item["number"])
        edit_responsavel = st.text_input("Responsável", value=item.get("responsavel") or "")
        save_col, remove_col = st.columns(2)
        with save_col:
            save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            remove = st.form_submit_button("Remover processo", use_container_width=True)
    if save:
        try:
            normalized = NumeroProcessoCNJ.parse(edit_number.strip()).bruto
            if any(
                i != index and other["number"] == normalized for i, other in enumerate(st.session_state.processes)
            ):
                st.warning("Esse processo já está na lista.")
            else:
                if st.session_state.process_number == item["number"]:
                    st.session_state.process_number = normalized
                st.session_state.processes[index] = {
                    "number": normalized,
                    "label": edit_label.strip() or "Processo monitorado",
                    "responsavel": edit_responsavel.strip(),
                }
                st.success("Processo atualizado.")
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if remove:
        removed = st.session_state.processes.pop(index)
        if st.session_state.process_number == removed["number"]:
            st.session_state.process_number = (
                st.session_state.processes[0]["number"] if st.session_state.processes else ""
            )
        st.success("Processo removido.")
        st.rerun()


@st.dialog("Editar CNPJ")
def show_edit_cnpj_dialog(index: int) -> None:
    item = st.session_state.monitored_cnpjs[index]
    with st.form("cnpj_edit_form"):
        edit_cnpj = st.text_input("CNPJ", value=format_cnpj_br(item["cnpj"]))
        edit_label = st.text_input("Nome da empresa / Razão Social", value=item["label"])
        edit_cliente = st.text_input("Nome do Cliente", value=item.get("cliente") or "")
        edit_responsavel = st.text_input("Responsável", value=item.get("responsavel") or "")
        save_col, remove_col = st.columns(2)
        with save_col:
            save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            remove = st.form_submit_button("Remover CNPJ", use_container_width=True)
    if save:
        digits = "".join(char for char in edit_cnpj if char.isdigit())
        if len(digits) != 14 or not edit_label.strip():
            st.warning("Informe um CNPJ válido e o nome da empresa.")
        elif any(i != index and other["cnpj"] == digits for i, other in enumerate(st.session_state.monitored_cnpjs)):
            st.warning("Esse CNPJ já está monitorado.")
        else:
            st.session_state.monitored_cnpjs[index] = {
                "cnpj": digits,
                "label": edit_label.strip(),
                "cliente": edit_cliente.strip(),
                "responsavel": edit_responsavel.strip(),
            }
            st.success("CNPJ atualizado.")
            st.rerun()
    if remove:
        st.session_state.monitored_cnpjs.pop(index)
        st.success("CNPJ removido.")
        st.rerun()


@st.dialog("Filtrar processos")
def show_process_filter_dialog() -> None:
    filters = st.session_state.setdefault("processo_filters", {"orgaos": []})
    orgao_options = sorted({resolve_orgao_label(p["number"]) for p in st.session_state.processes})
    selected_orgaos = st.multiselect(
        "Órgão", orgao_options, default=[o for o in filters["orgaos"] if o in orgao_options], key="processo_filter_orgaos_input"
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="processo_filter_apply", type="primary", use_container_width=True):
            st.session_state.processo_filters = {"orgaos": selected_orgaos}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="processo_filter_clear", use_container_width=True):
            st.session_state.processo_filters = {"orgaos": []}
            st.rerun()


@st.dialog("Cadastrar processo administrativo")
def show_add_sei_process_dialog(sei_org_name: str) -> None:
    with st.form(f"sei_form_{sei_org_name}", clear_on_submit=True):
        sei_number = st.text_input("Número do processo", placeholder="Ex.: 58000.012345/2026-11", key=f"sei_number_{sei_org_name}")
        sei_interessado = st.text_input("Interessado / Cliente", placeholder="Ex.: Federação X", key=f"sei_interessado_{sei_org_name}")
        sei_responsavel = st.text_input("Responsável", placeholder="Ex.: Advogado(a) responsável", key=f"sei_responsavel_{sei_org_name}")
        sei_sistema_origem = st.text_input("Sistema de origem", value="SEI", placeholder="Ex.: SEI", key=f"sei_sistema_{sei_org_name}")
        sei_tipo_col, sei_forma_col = st.columns(2)
        with sei_tipo_col:
            sei_tipo = st.selectbox("Tipo", SEI_TIPOS, key=f"sei_tipo_{sei_org_name}")
        with sei_forma_col:
            sei_forma_acesso = st.selectbox("Forma de acesso", SEI_FORMAS_ACESSO, key=f"sei_forma_{sei_org_name}")
        sei_add = st.form_submit_button("Cadastrar processo", use_container_width=True)
    if sei_add:
        if not sei_number.strip():
            st.warning("Informe o número do processo.")
        elif any(p["number"] == sei_number.strip() and p["org"] == sei_org_name for p in st.session_state.sei_processes):
            st.warning("Esse processo já está cadastrado para este órgão.")
        else:
            st.session_state.sei_processes.append({
                "number": sei_number.strip(),
                "org": sei_org_name,
                "interessado": sei_interessado.strip(),
                "responsavel": sei_responsavel.strip(),
                "sistema_origem": sei_sistema_origem.strip() or "SEI",
                "tipo": sei_tipo,
                "forma_acesso": sei_forma_acesso,
                "movements": [],
                "last_query": None,
            })
            st.success("Processo cadastrado.")
            st.rerun()


@st.dialog("Filtrar processos")
def show_sei_todos_filter_dialog() -> None:
    filters = st.session_state.setdefault("sei_todos_filters", {"orgaos": [], "status": []})
    orgao_options = sorted({p["org"] for p in st.session_state.sei_processes})
    selected_orgaos = st.multiselect(
        "Órgão", orgao_options, default=[o for o in filters["orgaos"] if o in orgao_options], key="sei_todos_filter_orgaos_input"
    )
    selected_status = st.multiselect(
        "Status do link",
        SEI_LINK_STATUS_CATEGORIES,
        default=[s for s in filters["status"] if s in SEI_LINK_STATUS_CATEGORIES],
        key="sei_todos_filter_status_input",
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="sei_todos_filter_apply", type="primary", use_container_width=True):
            st.session_state.sei_todos_filters = {"orgaos": selected_orgaos, "status": selected_status}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="sei_todos_filter_clear", use_container_width=True):
            st.session_state.sei_todos_filters = {"orgaos": [], "status": []}
            st.rerun()


@st.dialog("Filtrar processos")
def show_sei_filter_dialog(sei_org_name: str) -> None:
    state_key = f"sei_filters_{sei_org_name}"
    filters = st.session_state.setdefault(state_key, {"tipos": []})
    org_processes = [p for p in st.session_state.sei_processes if p["org"] == sei_org_name]
    tipo_options = sorted({p.get("tipo") for p in org_processes if p.get("tipo")})
    selected_tipos = st.multiselect(
        "Tipo", tipo_options, default=[t for t in filters["tipos"] if t in tipo_options], key=f"sei_filter_tipos_input_{sei_org_name}"
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key=f"sei_filter_apply_{sei_org_name}", type="primary", use_container_width=True):
            st.session_state[state_key] = {"tipos": selected_tipos}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key=f"sei_filter_clear_{sei_org_name}", use_container_width=True):
            st.session_state[state_key] = {"tipos": []}
            st.rerun()


@st.dialog("Editar processo administrativo")
def show_edit_sei_process_dialog(index: int) -> None:
    item = st.session_state.sei_processes[index]
    with st.form("sei_edit_form"):
        edit_number = st.text_input("Número do processo", value=item["number"])
        edit_org = st.selectbox("Órgão", SEI_ORGAOS, index=SEI_ORGAOS.index(item["org"]) if item["org"] in SEI_ORGAOS else 0)
        edit_interessado = st.text_input("Interessado / Cliente", value=item.get("interessado") or "")
        edit_responsavel = st.text_input("Responsável", value=item.get("responsavel") or "")
        edit_sistema_origem = st.text_input("Sistema de origem", value=item.get("sistema_origem") or "SEI")
        edit_tipo_col, edit_forma_col = st.columns(2)
        with edit_tipo_col:
            edit_tipo = st.selectbox(
                "Tipo", SEI_TIPOS, index=SEI_TIPOS.index(item["tipo"]) if item.get("tipo") in SEI_TIPOS else 0
            )
        with edit_forma_col:
            edit_forma_acesso = st.selectbox(
                "Forma de acesso",
                SEI_FORMAS_ACESSO,
                index=SEI_FORMAS_ACESSO.index(item["forma_acesso"]) if item.get("forma_acesso") in SEI_FORMAS_ACESSO else 0,
            )
        save_col, remove_col = st.columns(2)
        with save_col:
            save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            remove = st.form_submit_button("Remover processo", use_container_width=True)
    if save:
        if not edit_number.strip():
            st.warning("Informe o número do processo.")
        elif any(
            i != index and p["number"] == edit_number.strip() and p["org"] == edit_org
            for i, p in enumerate(st.session_state.sei_processes)
        ):
            st.warning("Esse processo já está cadastrado para este órgão.")
        else:
            st.session_state.sei_processes[index] = {
                **item,
                "number": edit_number.strip(),
                "org": edit_org,
                "interessado": edit_interessado.strip(),
                "responsavel": edit_responsavel.strip(),
                "sistema_origem": edit_sistema_origem.strip() or "SEI",
                "tipo": edit_tipo,
                "forma_acesso": edit_forma_acesso,
            }
            st.success("Processo atualizado.")
            st.rerun()
    if remove:
        st.session_state.sei_processes.pop(index)
        st.success("Processo removido.")
        st.rerun()


PLATAFORMAS = ["DJe", "DET", "SEI", "TCU"]

if "active_module" not in st.session_state:
    st.session_state.active_module = None


MONITORAMENTO_INFO = {
    "DJe": (
        "A consulta usa APIs públicas oficiais e não exige autenticação nem credencial. Na aba Processos, "
        "busca movimentações no DataJud (CNJ) e publicações no Diário de Justiça Eletrônico Nacional (DJEN) a "
        "partir do número CNJ do processo. Na aba CNPJ, a busca é feita **apenas no DJEN**, pela razão social "
        "do CNPJ monitorado — a API própria do DJe ainda não tem integração implementada."
    ),
    "DET": (
        "Conector aguardando credenciais oficiais do Domicílio Eletrônico Trabalhista (DET). Quando integrado, "
        "buscará comunicações trabalhistas vinculadas aos CNPJs autorizados pelo escritório."
    ),
    "SEI": (
        "A consulta abre o link de acesso externo cadastrado para o processo administrativo no portal do órgão "
        "emissor (Sistema Eletrônico de Informações). O histórico de movimentações é capturado manualmente a "
        "partir dessa consulta, já que cada órgão publica em seu próprio SEI."
    ),
    "TCU": (
        "Conector aguardando credenciais oficiais do Tribunal de Contas da União. Quando integrado, buscará "
        "acórdãos, processos e comunicações de interesse do escritório."
    ),
}


@st.dialog("Como funciona esta consulta")
def show_monitoramento_info_dialog(sistema: str) -> None:
    st.markdown(f'<div class="eyebrow">{html.escape(sistema)}</div>', unsafe_allow_html=True)
    st.write(MONITORAMENTO_INFO.get(sistema, "Informações não disponíveis para este sistema."))


@st.dialog("Configurações")
def show_settings_dialog() -> None:
    st.markdown('<div class="eyebrow">PALETA DE CORES</div>', unsafe_allow_html=True)
    for palette_name, colors in COLOR_PALETTES.items():
        swatch_html = "".join(
            '<span style="display:inline-block;width:22px;height:22px;border-radius:5px;margin-right:6px;'
            f'border:1px solid rgba(0,0,0,.15);background:{colors[key]};"></span>'
            for key in ["surface", "ink", "teal", "teal-dark", "yellow"]
        )
        row_label_col, row_action_col = st.columns([3, 1])
        with row_label_col:
            st.markdown(
                f'<div style="display:flex;align-items:center;margin:.6rem 0;">{swatch_html}'
                f'<span style="margin-left:8px;font-weight:600;">{palette_name}</span></div>',
                unsafe_allow_html=True,
            )
        with row_action_col:
            is_current = st.session_state.color_palette == palette_name
            if st.button(
                "Selecionada" if is_current else "Usar",
                key=f"apply_palette_{palette_name}",
                use_container_width=True,
                disabled=is_current,
            ):
                st.session_state.color_palette = palette_name
                st.rerun()


if "firm_profile" not in st.session_state:
    st.session_state.firm_profile = {
        "usuario": "Vinícius Feijó",
        "nome": "Camargos Advogados",
        "cnpj": "",
        "endereco": "",
        "area_atuacao": "",
        "telefone": "(11) 99999-9999",
        "email": "viniciusfeijo360@gmail.com",
        "logo": None,
    }


@st.dialog("Perfil do escritório")
def show_profile_dialog() -> None:
    profile = st.session_state.firm_profile
    if profile.get("logo"):
        st.image(profile["logo"], width=72)
    logo_upload = st.file_uploader("Logo do escritório", type=["png", "jpg", "jpeg"], key="firm_logo_upload")
    with st.form("firm_profile_form"):
        usuario = st.text_input("Nome do Usuário", value=profile.get("usuario", ""), placeholder="Ex.: Dra. Camargos")
        nome = st.text_input("Nome do Escritório", value=profile.get("nome", ""))
        cnpj = st.text_input("CNPJ", value=profile.get("cnpj", ""), placeholder="00.000.000/0000-00")
        endereco = st.text_input("Endereço", value=profile.get("endereco", ""), placeholder="Ex.: Av. Paulista, 1000 · São Paulo/SP")
        area_atuacao = st.text_input("Área de Atuação", value=profile.get("area_atuacao", ""), placeholder="Ex.: Direito Administrativo e Esportivo")
        tel_col, email_col = st.columns(2)
        with tel_col:
            telefone = st.text_input("Telefone", value=profile.get("telefone", ""), placeholder="(00) 00000-0000")
        with email_col:
            email = st.text_input("E-mail", value=profile.get("email", ""), placeholder="contato@escritorio.com.br")
        save = st.form_submit_button("Salvar", type="primary", use_container_width=True)
    if save:
        if not nome.strip():
            st.warning("Informe o nome do escritório.")
        else:
            logo_data_url = profile.get("logo")
            if logo_upload is not None:
                encoded = base64.b64encode(logo_upload.getvalue()).decode("ascii")
                logo_data_url = f"data:{logo_upload.type};base64,{encoded}"
            st.session_state.firm_profile = {
                "usuario": usuario.strip(),
                "nome": nome.strip(),
                "cnpj": cnpj.strip(),
                "endereco": endereco.strip(),
                "area_atuacao": area_atuacao.strip(),
                "telefone": telefone.strip(),
                "email": email.strip(),
                "logo": logo_data_url,
            }
            st.success("Perfil atualizado.")
            st.rerun()


with st.sidebar:
    with st.container(key="sidebar_brand"):
        brand_icon_col, brand_text_col = st.columns([1, 4])
        with brand_icon_col:
            _app_logo_file = COLOR_PALETTES[st.session_state.color_palette]["app-logo"]
            st.markdown(
                f'<img src="{load_logo_data_uri(_app_logo_file)}" class="brand-logo-icon" />', unsafe_allow_html=True
            )
        with brand_text_col:
            st.markdown(
                '<div class="brand-title">GestorJus</div><div class="brand-subtitle">central jurídica</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    _active_module = st.session_state.active_module

    if st.button(
        ":material/home: Home",
        key="nav_home_button",
        type="primary" if _active_module is None else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = None
        st.rerun()

    if st.button(
        ":material/space_dashboard: Painel Geral",
        key="nav_painel_button",
        type="primary" if _active_module == "Painel Geral" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Painel Geral"
        st.rerun()

    if st.button(
        ":material/monitoring: Monitoramento",
        key="nav_monitoramento_button",
        type="primary" if _active_module == "Monitoramento" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Monitoramento"
        st.rerun()

    if st.button(
        ":material/app_registration: Cadastro",
        key="nav_cadastro_button",
        type="primary" if _active_module == "Cadastro" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Cadastro"
        st.rerun()

    module = st.session_state.active_module

    st.divider()

    if st.button(
        ":material/key: Links e Autenticações",
        key="nav_links_button",
        type="primary" if _active_module == "Links e Autenticações" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Links e Autenticações"
        st.rerun()

    if st.button(":material/settings: Configurações", key="nav_settings_button", use_container_width=True):
        show_settings_dialog()

    st.divider()
    st.caption("AMBIENTE PILOTO")
    st.caption("v0.1 · debug local")

if "process_number" not in st.session_state:
    st.session_state.process_number = st.session_state.processes[0]["number"] if st.session_state.processes else ""
process_number = st.session_state.process_number

if module is None:
    usuario_nome = st.session_state.firm_profile.get("usuario", "").strip()
    welcome_title = f"Bem-vindo ao GestorJus, {html.escape(usuario_nome)}" if usuario_nome else "Bem-vindo ao GestorJus"
    st.markdown(
        '<div class="welcome-screen">'
        f'<h1>{welcome_title}</h1>'
        '<div class="lede">A plataforma que gerencia e automatiza o acompanhamento processual do seu escritório.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    profile = st.session_state.firm_profile
    id_card_office = html.escape(profile.get("nome") or "Escritório")
    id_card_name = html.escape(profile.get("usuario") or "Usuário não informado")
    id_card_email = html.escape(profile.get("email") or "e-mail não informado")
    id_card_endereco = html.escape(profile.get("endereco") or "endereço não informado")
    id_card_telefone = html.escape(profile.get("telefone") or "telefone não informado")

    id_card_photo_html = (
        f'<img src="{profile["logo"]}" class="id-card-photo" />' if profile.get("logo") else '<div class="id-card-photo">GJ</div>'
    )

    with st.container(key="home_profile_panel"):
        with st.container(key="profile_id_card"):
            st.markdown(
                '<div class="id-card">'
                f'{id_card_photo_html}'
                '<div class="id-card-info">'
                f'<div class="id-card-username">{id_card_name}</div>'
                f'<div class="id-card-office">{id_card_office}</div>'
                f'<div class="id-card-contact">{id_card_email} · {id_card_telefone}</div>'
                f'<div class="id-card-contact">{id_card_endereco}</div>'
                '</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("Editar perfil do escritório", key="open_profile_card_button"):
                show_profile_dialog()

        with st.container(key="logout_button_wrap"):
            st.button(
                "Fazer Logout",
                key="logout_button",
                help="Ainda não disponível — módulo de autenticação em desenvolvimento",
                disabled=True,
                use_container_width=True,
            )

elif module == "Painel Geral":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Painel Geral.</h1>'
        '<div class="lede">Visão consolidada de todos os processos, CNPJs e órgãos monitorados pelo escritório, '
        'reunidos em um único lugar.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="eyebrow">TODOS OS ITENS MONITORADOS</div>', unsafe_allow_html=True)

    def _abrir_dialog_painel_processo(kind: str, item: dict) -> None:
        if kind == "DJe":
            show_movimentacoes_dialog(
                f"{item['label']} · {item['number']}",
                nav_state={
                    "consulta_select_process": f"{item['label']} · {item['number']}",
                    "_nav_platform": "DJe",
                    "_nav_dje_subtab": "Processos",
                },
                ultima_atualizacao=st.session_state.query_timestamps.get(item["number"]),
                consultar_action=lambda numero=item["number"]: consultar_dje_processo(numero),
                refresh=lambda numero=item["number"]: {
                    "sources": {
                        "Movimentações (DataJud)": dje_datajud_rows(numero),
                        "Diário (DJEN)": dje_djen_rows(numero),
                    },
                    "ultima_atualizacao": st.session_state.query_timestamps.get(numero),
                },
                sources={
                    "Movimentações (DataJud)": dje_datajud_rows(item["number"]),
                    "Diário (DJEN)": dje_djen_rows(item["number"]),
                },
                default_source="Movimentações (DataJud)",
            )
        else:
            show_movimentacoes_dialog(
                f"{item['org']} · {item['number']}",
                movimentacoes_sei_processo(item),
                nav_state={
                    "_nav_platform": "SEI",
                    "_nav_sei_org": item["org"],
                    "_nav_sei_process": item["number"],
                },
                ultima_atualizacao=item.get("last_query"),
                consultar_link=(find_credencial_for_processo(item["number"]) or {}).get("link"),
                consultar_proc=item,
            )

    painel_tab_processos, painel_tab_cnpj = st.tabs(["Processos", "CNPJ"])

    with painel_tab_processos:
        if not st.session_state.processes and not st.session_state.sei_processes:
            status("Nenhum processo monitorado ainda. Cadastre um processo para começar.", "warn")
        else:
            painel_proc_refs = [("DJe", item) for item in st.session_state.processes] + [
                ("SEI", item) for item in st.session_state.sei_processes
            ]
            painel_proc_rows = [
                {
                    "Sistema": kind,
                    "Órgão": resolve_orgao_label(item["number"]) if kind == "DJe" else item["org"],
                    "Referência": item["label"] if kind == "DJe" else (item.get("interessado") or "não informado"),
                    "Número do processo": item["number"],
                    "Responsável": item.get("responsavel") or "não informado",
                }
                for kind, item in painel_proc_refs
            ]
            selection = st.dataframe(
                painel_proc_rows,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="painel_proc_table",
            )
            st.caption("Selecione uma linha para ver as últimas movimentações.")
            selected_rows = selection.get("selection", {}).get("rows", []) if selection else []
            if st.button(
                "Ver histórico de movimentações",
                key="painel_proc_ver_historico",
                disabled=not selected_rows,
                use_container_width=True,
            ):
                kind, item = painel_proc_refs[selected_rows[0]]
                _abrir_dialog_painel_processo(kind, item)

    with painel_tab_cnpj:
        if not st.session_state.monitored_cnpjs:
            status("Nenhum CNPJ monitorado ainda. Cadastre um CNPJ para começar.", "warn")
        else:
            painel_cnpj_rows = [
                {
                    "Sistema": "DJe",
                    "Razão Social": item["label"],
                    "CNPJ": format_cnpj_br(item["cnpj"]),
                    "Cliente": item.get("cliente") or "não informado",
                    "Responsável": item.get("responsavel") or "não informado",
                }
                for item in st.session_state.monitored_cnpjs
            ]
            cnpj_selection = st.dataframe(
                painel_cnpj_rows,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="painel_cnpj_table",
            )
            st.caption("Selecione uma linha para ver as últimas movimentações.")
            cnpj_selected_rows = cnpj_selection.get("selection", {}).get("rows", []) if cnpj_selection else []
            if st.button(
                "Ver histórico de movimentações",
                key="painel_cnpj_ver_historico",
                disabled=not cnpj_selected_rows,
                use_container_width=True,
            ):
                item = st.session_state.monitored_cnpjs[cnpj_selected_rows[0]]
                show_movimentacoes_dialog(
                    item["label"],
                    nav_state={
                        "consulta_select_cnpj": f"{item['label']} · {format_cnpj_br(item['cnpj'])}",
                        "_nav_platform": "DJe",
                        "_nav_dje_subtab": "CNPJ",
                    },
                    ultima_atualizacao=st.session_state.cnpj_query_timestamps.get(item["cnpj"]),
                    consultar_action=lambda cnpj_item=item: consultar_dje_cnpj(cnpj_item),
                    refresh=lambda cnpj_item=item: {
                        "sources": {
                            "Movimentações (DJe)": [],
                            "Diário (DJEN)": movimentacoes_cnpj(cnpj_item["cnpj"]),
                        },
                        "ultima_atualizacao": st.session_state.cnpj_query_timestamps.get(cnpj_item["cnpj"]),
                    },
                    sources={
                        "Movimentações (DJe)": [],
                        "Diário (DJEN)": movimentacoes_cnpj(item["cnpj"]),
                    },
                    default_source="Diário (DJEN)",
                    unavailable_sources={"Movimentações (DJe)": DJE_CNPJ_NOT_IMPLEMENTED_MSG},
                )

elif module == "Monitoramento":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Monitoramento.</h1>'
        '<div class="lede">Selecione o órgão/sistema que deseja monitorar. Cada aba explica como a consulta é '
        'feita antes de você iniciá-la.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    _nav_platform_target = st.session_state.pop("_nav_platform", None)
    mon_tab_dje, mon_tab_det, mon_tab_sei, mon_tab_tcu = st.tabs(
        PLATAFORMAS, default=_nav_platform_target or PLATAFORMAS[0]
    )

    with mon_tab_dje:
        _nav_dje_subtab_target = st.session_state.pop("_nav_dje_subtab", None)
        mon_cons_tab_cnpj, mon_cons_tab_cnj = st.tabs(
            ["CNPJ", "Processos"], default=_nav_dje_subtab_target or "CNPJ"
        )

        with mon_cons_tab_cnj:
            if not st.session_state.processes:
                status("Nenhum processo cadastrado ainda. Cadastre um processo para consultar.", "warn")
            else:
                process_options = [f"{item['label']} · {item['number']}" for item in st.session_state.processes]
                current_number = st.session_state.process_number
                default_index = next(
                    (i for i, item in enumerate(st.session_state.processes) if item["number"] == current_number), 0
                )
                select_process_col, periodo_col = st.columns([2, 3])
                with select_process_col:
                    st.markdown('<div class="eyebrow">Selecionar processo:</div>', unsafe_allow_html=True)
                    selected_process = st.selectbox(
                        "Selecionar processo para consulta",
                        process_options,
                        index=default_index,
                        key="consulta_select_process",
                        label_visibility="collapsed",
                    )
                periodo_data_inicial, periodo_data_final = render_periodo_selector_row("dje_processo", periodo_col)
                selected_index = process_options.index(selected_process)
                st.session_state.process_number = st.session_state.processes[selected_index]["number"]
                process_number = st.session_state.process_number
                selected_label = st.session_state.processes[selected_index]["label"]

                consultar_col, info_col = st.columns([4, 1])
                with consultar_col:
                    consultar_dje_clicked = st.button(
                        "Consultar movimentações", type="primary", use_container_width=True, key="consultar_dje_processo"
                    )
                with info_col:
                    if st.button("Informações", key="info_dje_processo", use_container_width=True):
                        show_monitoramento_info_dialog("DJe")

                if consultar_dje_clicked:
                    with st.spinner("Consultando DataJud e DJEN..."):
                        consultar_dje_processo(process_number)

                djen_response = st.session_state.djen_results.get(process_number)
                datajud_result = st.session_state.datajud_results.get(process_number)
                last_query = st.session_state.query_timestamps.get(process_number)

                datajud_rows = dje_datajud_rows(process_number)
                djen_rows = dje_djen_rows(process_number)

                datajud_rows_periodo = filter_rows_by_date_range(datajud_rows, periodo_data_inicial, periodo_data_final)
                djen_rows_periodo = filter_rows_by_date_range(djen_rows, periodo_data_inicial, periodo_data_final)

                summary_a, summary_b, summary_c = st.columns(3)
                with summary_a:
                    movements_found = len(datajud_rows_periodo) if datajud_result else "—"
                    card("MOVIMENTAÇÕES ENCONTRADAS", str(movements_found), "DataJud")
                with summary_b:
                    publications_found = str(len(djen_rows_periodo)) if djen_response else "—"
                    card("PUBLICAÇÕES NO DIÁRIO", publications_found, "DJEN")
                with summary_c:
                    last_query_label = last_query.strftime("%d/%m/%Y %H:%M") if last_query else "—"
                    card("ÚLTIMA CONSULTA", last_query_label, "data e hora")

                if datajud_result:
                    source = datajud_result["source"]
                    assuntos = ", ".join(a.get("nome", "") for a in source.get("assuntos", []) if a.get("nome")) or "não informado"
                    st.markdown('<div class="eyebrow" style="margin-top:1.2rem;">Dados do processo:</div>', unsafe_allow_html=True)
                    st.markdown(
                        f"**Classe:** {source.get('classe', {}).get('nome', 'não informada')} &nbsp;·&nbsp; "
                        f"**Assunto:** {assuntos} &nbsp;·&nbsp; "
                        f"**Grau:** {source.get('grau', 'não informado')} &nbsp;·&nbsp; "
                        f"**Sistema:** {source.get('sistema', {}).get('nome', 'não informado')} &nbsp;·&nbsp; "
                        f"**Ajuizamento:** {format_date_br(source.get('dataAjuizamento')) or 'não informado'}"
                    )

                if datajud_rows or djen_rows:
                    timeline_source = st.segmented_control(
                        "Fonte",
                        ["Movimentações (DataJud)", "Diário (DJEN)"],
                        default="Movimentações (DataJud)",
                        key="timeline_source",
                        label_visibility="collapsed",
                    ) or "Movimentações (DataJud)"
                    timeline_rows_all = datajud_rows if timeline_source == "Movimentações (DataJud)" else djen_rows
                    timeline_rows = filter_rows_by_date_range(timeline_rows_all, periodo_data_inicial, periodo_data_final)
                    if timeline_rows:
                        timeline_rows = sorted(timeline_rows, key=lambda row: row.get("Data") or date.min)
                        column_config = {"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")}
                        if "Origem" in timeline_rows[0]:
                            column_config["Origem"] = st.column_config.LinkColumn("Origem", display_text="Abrir ↗")
                        st.dataframe(timeline_rows, use_container_width=True, hide_index=True, column_config=column_config)
                    elif timeline_rows_all and (periodo_data_inicial or periodo_data_final):
                        status("Nenhuma movimentação encontrada no período selecionado.", "warn")
                    else:
                        status("Nenhum registro disponível para esta visualização ainda.")

        with mon_cons_tab_cnpj:
            if not st.session_state.monitored_cnpjs:
                status("Nenhum CNPJ cadastrado ainda. Cadastre um CNPJ para consultar.", "warn")
            else:
                cnpj_options = [f"{item['label']} · {format_cnpj_br(item['cnpj'])}" for item in st.session_state.monitored_cnpjs]

                select_cnpj_col, cnpj_periodo_col = st.columns([2, 3])
                with select_cnpj_col:
                    st.markdown('<div class="eyebrow">Selecionar CNPJ:</div>', unsafe_allow_html=True)
                    selected_cnpj_option = st.selectbox(
                        "Selecionar CNPJ para consulta",
                        cnpj_options,
                        key="consulta_select_cnpj",
                        label_visibility="collapsed",
                    )
                periodo_cnpj_data_inicial, periodo_cnpj_data_final = render_periodo_selector_row(
                    "dje_cnpj", cnpj_periodo_col
                )

                selected_cnpj_index = cnpj_options.index(selected_cnpj_option)
                selected_cnpj_item = st.session_state.monitored_cnpjs[selected_cnpj_index]
                cnpj_key = selected_cnpj_item["cnpj"]

                consultar_cnpj_col, info_cnpj_col = st.columns([4, 1])
                with consultar_cnpj_col:
                    consultar_cnpj_clicked = st.button(
                        "Consultar movimentações", type="primary", use_container_width=True, key="consult_cnpj"
                    )
                with info_cnpj_col:
                    if st.button("Informações", key="info_dje_cnpj", use_container_width=True):
                        show_monitoramento_info_dialog("DJe")

                if consultar_cnpj_clicked:
                    with st.spinner("Consultando o DJe e DJEN..."):
                        consultar_dje_cnpj(selected_cnpj_item)

                djen_cnpj_response = st.session_state.djen_cnpj_results.get(cnpj_key)
                last_cnpj_query = st.session_state.cnpj_query_timestamps.get(cnpj_key)

                cnpj_djen_rows_all = movimentacoes_cnpj(cnpj_key)
                cnpj_djen_rows_periodo = filter_rows_by_date_range(
                    cnpj_djen_rows_all, periodo_cnpj_data_inicial, periodo_cnpj_data_final
                )

                summary_cnpj_a, summary_cnpj_b = st.columns(2)
                with summary_cnpj_a:
                    publications_found = str(len(cnpj_djen_rows_periodo)) if djen_cnpj_response else "—"
                    card("PUBLICAÇÕES NO DIÁRIO", publications_found, "DJEN")
                with summary_cnpj_b:
                    last_cnpj_query_label = last_cnpj_query.strftime("%d/%m/%Y %H:%M") if last_cnpj_query else "—"
                    card("ÚLTIMA CONSULTA", last_cnpj_query_label, "data e hora")

                if cnpj_djen_rows_all:
                    cnpj_timeline_source = st.segmented_control(
                        "Fonte",
                        ["Movimentações (DJe)", "Diário (DJEN)"],
                        default="Diário (DJEN)",
                        key="cnpj_timeline_source",
                        label_visibility="collapsed",
                    ) or "Diário (DJEN)"
                    if cnpj_timeline_source == "Movimentações (DJe)":
                        status(DJE_CNPJ_NOT_IMPLEMENTED_MSG)
                    else:
                        cnpj_timeline_rows = filter_rows_by_date_range(
                            cnpj_djen_rows_all, periodo_cnpj_data_inicial, periodo_cnpj_data_final
                        )
                        if cnpj_timeline_rows:
                            cnpj_timeline_rows = sorted(cnpj_timeline_rows, key=lambda row: row.get("Data") or date.min)
                            st.dataframe(
                                cnpj_timeline_rows,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                                    "Origem": st.column_config.LinkColumn("Origem", display_text="Abrir ↗"),
                                },
                            )
                        elif cnpj_djen_rows_all and (periodo_cnpj_data_inicial or periodo_cnpj_data_final):
                            status("Nenhuma movimentação encontrada no período selecionado.", "warn")
                        else:
                            status("Nenhum registro disponível para esta visualização ainda.")
                else:
                    status("Nenhum registro disponível para esta visualização ainda.")

    with mon_tab_det:
        det_consultar_col, det_info_col = st.columns([4, 1])
        with det_consultar_col:
            st.button("Consultar DET", disabled=True, use_container_width=True, key="consultar_det")
        with det_info_col:
            if st.button("Informações", key="info_det", use_container_width=True):
                show_monitoramento_info_dialog("DET")

    with mon_tab_sei:

        SEI_TODOS_ORGAOS = "Todos os Órgãos"
        sei_cons_tab_labels = [SEI_TODOS_ORGAOS] + SEI_ORGAOS
        _nav_sei_org_target = st.session_state.pop("_nav_sei_org", None)
        _nav_sei_process_target = st.session_state.pop("_nav_sei_process", None)
        sei_cons_tabs = st.tabs(sei_cons_tab_labels, default=_nav_sei_org_target or sei_cons_tab_labels[0])

        with sei_cons_tabs[0]:
            st.session_state.setdefault("sei_todos_filters", {"orgaos": [], "status": []})
            search_col, filter_col = st.columns([5, 1])
            with search_col:
                st.markdown('<div class="eyebrow">Buscar processo:</div>', unsafe_allow_html=True)
                sei_search_all = st.text_input(
                    "Buscar processo",
                    placeholder="Buscar por número, interessado ou órgão",
                    key="sei_search_todos",
                    label_visibility="collapsed",
                )
            with filter_col:
                st.markdown('<div class="eyebrow">&nbsp;</div>', unsafe_allow_html=True)
                if st.button(
                    ":material/filter_alt:", key="toolbar_filter_sei_todos", help="Filtrar", use_container_width=True
                ):
                    show_sei_todos_filter_dialog()

            sei_todos_filters = st.session_state["sei_todos_filters"]
            filtered_all = st.session_state.sei_processes
            if sei_todos_filters["orgaos"]:
                filtered_all = [p for p in filtered_all if p["org"] in sei_todos_filters["orgaos"]]
            if sei_todos_filters["status"]:
                filtered_all = [p for p in filtered_all if sei_link_status(p)[1] in sei_todos_filters["status"]]
            if sei_search_all.strip():
                term_all = sei_search_all.strip().lower()
                filtered_all = [
                    p for p in filtered_all
                    if term_all in p["number"].lower()
                    or term_all in (p.get("interessado") or "").lower()
                    or term_all in p["org"].lower()
                ]

            if not filtered_all:
                status("Nenhum processo encontrado para os filtros selecionados.")
            else:
                table_rows = [
                    {
                        "Número": proc["number"],
                        "Órgão": proc["org"],
                        "Interessado": proc.get("interessado") or "não informado",
                        "Responsável": proc.get("responsavel") or "não informado",
                        "Link de acesso": (find_credencial_for_processo(proc["number"]) or {}).get("link"),
                        "Status do link": sei_link_status(proc)[0],
                    }
                    for proc in filtered_all
                ]
                selection = st.dataframe(
                    table_rows,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="sei_todos_table",
                    column_config={
                        "Link de acesso": st.column_config.LinkColumn("Link de acesso", display_text="Abrir ↗"),
                    },
                )
                st.caption("Selecione uma linha para ver as movimentações do processo.")
                selected_rows = selection.get("selection", {}).get("rows", []) if selection else []
                if st.button(
                    "Ver histórico de movimentações",
                    key="sei_todos_ver_historico",
                    disabled=not selected_rows,
                    use_container_width=True,
                ):
                    selected_proc = filtered_all[selected_rows[0]]
                    show_movimentacoes_dialog(
                        f"{selected_proc['org']} · {selected_proc['number']}",
                        movimentacoes_sei_processo(selected_proc),
                        ultima_atualizacao=selected_proc.get("last_query"),
                        consultar_link=(find_credencial_for_processo(selected_proc["number"]) or {}).get("link"),
                        consultar_proc=selected_proc,
                    )

        for sei_org_tab, sei_org_name in zip(sei_cons_tabs[1:], SEI_ORGAOS):
            with sei_org_tab:
                org_processes = [p for p in st.session_state.sei_processes if p["org"] == sei_org_name]

                if not org_processes:
                    status(f"Nenhum processo cadastrado para {sei_org_name}. Cadastre um processo para consultar.", "warn")
                else:
                    process_options = [
                        f"{p['number']} · {p.get('interessado') or 'sem interessado'}" for p in org_processes
                    ]
                    default_index = 0
                    if _nav_sei_org_target == sei_org_name and _nav_sei_process_target:
                        default_index = next(
                            (i for i, p in enumerate(org_processes) if p["number"] == _nav_sei_process_target), 0
                        )
                    select_process_col, _spacer_col = st.columns([2, 3])
                    with select_process_col:
                        st.markdown('<div class="eyebrow">Selecionar processo:</div>', unsafe_allow_html=True)
                        selected_process = st.selectbox(
                            "Selecionar processo para consulta",
                            process_options,
                            index=default_index,
                            key=f"sei_select_process_{sei_org_name}",
                            label_visibility="collapsed",
                        )
                    selected_index = process_options.index(selected_process)
                    proc = org_processes[selected_index]

                    credencial = find_credencial_for_processo(proc["number"])
                    link = credencial["link"] if credencial and credencial.get("link") else None

                    consultar_col, info_col = st.columns([4, 1])
                    with consultar_col:
                        st.link_button(
                            "Consultar movimentações",
                            link or "#",
                            type="primary",
                            use_container_width=True,
                            disabled=not link,
                            on_click=lambda proc=proc: proc.__setitem__("last_query", datetime.now()),
                            key=f"consultar_sei_{sei_org_name}",
                        )
                    with info_col:
                        if st.button("Informações", key=f"info_sei_{sei_org_name}", use_container_width=True):
                            show_monitoramento_info_dialog("SEI")

                    if not link:
                        status("Link de acesso não cadastrado para este processo. Cadastre em Links e Autenticações.", "warn")

                    ultima_data, ultima_descricao = ultima_movimentacao_sei(proc)
                    last_query = proc.get("last_query")

                    summary_a, summary_b, summary_c = st.columns(3)
                    with summary_a:
                        card(
                            "INTERESSADO",
                            proc.get("interessado") or "não informado",
                            proc.get("responsavel") or "sem responsável",
                        )
                    with summary_b:
                        card(
                            "ÚLTIMA MOVIMENTAÇÃO",
                            ultima_data.strftime("%d/%m/%Y") if ultima_data else "—",
                            ultima_descricao or "sem registro",
                        )
                    with summary_c:
                        last_query_label = last_query.strftime("%d/%m/%Y %H:%M") if last_query else "—"
                        card("ÚLTIMA CONSULTA", last_query_label, "data e hora")

                    st.markdown(
                        '<div class="eyebrow" style="margin-top:1.2rem;">Movimentações registradas:</div>',
                        unsafe_allow_html=True,
                    )
                    mov_rows = movimentacoes_sei_processo(proc)
                    if mov_rows:
                        mov_rows_sorted = sorted(mov_rows, key=lambda r: r.get("Data") or date.min, reverse=True)
                        st.dataframe(
                            mov_rows_sorted,
                            use_container_width=True,
                            hide_index=True,
                            column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
                        )
                    else:
                        status("Nenhuma movimentação registrada ainda para este processo.")

    with mon_tab_tcu:
        tcu_consultar_col, tcu_info_col = st.columns([4, 1])
        with tcu_consultar_col:
            st.button("Consultar TCU", disabled=True, use_container_width=True, key="consultar_tcu")
        with tcu_info_col:
            if st.button("Informações", key="info_tcu", use_container_width=True):
                show_monitoramento_info_dialog("TCU")

elif module == "Cadastro":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Cadastro.</h1>'
        '<div class="lede">Cadastre processos e CNPJs monitorados de qualquer sistema, tudo em um único lugar.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    CADASTRO_SISTEMAS = ["DJe", "SEI"]

    def _on_cadastro_sistema_change() -> None:
        st.session_state.cadastro_sistema = st.session_state.cadastro_sistema_select

    st.markdown('<div class="eyebrow">Selecionar sistema:</div>', unsafe_allow_html=True)
    st.session_state.setdefault("cadastro_sistema", None)
    current_cadastro_sistema = st.session_state.cadastro_sistema if st.session_state.cadastro_sistema in CADASTRO_SISTEMAS else None
    st.selectbox(
        "Selecionar sistema",
        CADASTRO_SISTEMAS,
        index=CADASTRO_SISTEMAS.index(current_cadastro_sistema) if current_cadastro_sistema else None,
        placeholder="Selecione o sistema",
        key="cadastro_sistema_select",
        on_change=_on_cadastro_sistema_change,
        label_visibility="collapsed",
    )
    cadastro_sistema = st.session_state.cadastro_sistema

    if cadastro_sistema == "DJe":
        cad_tab_cnpj, cad_tab_cnj = st.tabs(["CNPJ", "Processos"])

        with cad_tab_cnj:
            st.session_state.setdefault("processo_delete_open", False)
            st.session_state.setdefault("processo_filters", {"orgaos": []})

            with st.container(key="processo_toolbar"):
                if st.button(":material/filter_alt:", key="toolbar_filter_processo", help="Filtrar"):
                    show_process_filter_dialog()
                if st.button(":material/add:", key="toolbar_add_processo", help="Cadastrar processo"):
                    show_add_process_dialog()
                if st.button(":material/delete:", key="toolbar_delete_processo", help="Excluir"):
                    st.session_state.processo_delete_open = not st.session_state.processo_delete_open

            if st.session_state.processo_delete_open and st.session_state.processes:
                delete_options = [f"{item['label']} · {item['number']}" for item in st.session_state.processes]
                del_col, confirm_col = st.columns([3, 1])
                with del_col:
                    delete_choice = st.selectbox(
                        "Selecionar processo para excluir", delete_options, label_visibility="collapsed", key="processo_delete_select"
                    )
                with confirm_col:
                    if st.button("Excluir", key="processo_delete_confirm", use_container_width=True):
                        idx = delete_options.index(delete_choice)
                        removed = st.session_state.processes.pop(idx)
                        if st.session_state.process_number == removed["number"]:
                            st.session_state.process_number = (
                                st.session_state.processes[0]["number"] if st.session_state.processes else ""
                            )
                        st.session_state.processo_delete_open = False
                        st.success("Processo removido.")
                        st.rerun()

            processo_filters = st.session_state.processo_filters
            filtered_processes = st.session_state.processes
            if processo_filters["orgaos"]:
                filtered_processes = [
                    p for p in filtered_processes if resolve_orgao_label(p["number"]) in processo_filters["orgaos"]
                ]

            if not filtered_processes:
                status("Nenhum processo cadastrado ainda.")
            else:
                orig_index_by_number = {p["number"]: i for i, p in enumerate(st.session_state.processes)}
                ratios = [2, 3, 3, 2, 1]
                header_cols = st.columns(ratios)
                for col, label in zip(header_cols, ["Órgão", "Cliente", "Número do processo", "Responsável", ""]):
                    with col:
                        st.markdown(f'<div class="painel-row-th">{html.escape(label)}</div>', unsafe_allow_html=True)
                for p in filtered_processes:
                    row_cols = st.columns(ratios)
                    row_cols[0].markdown(f'<div class="painel-row-td">{html.escape(resolve_orgao_label(p["number"]))}</div>', unsafe_allow_html=True)
                    row_cols[1].markdown(f'<div class="painel-row-td">{html.escape(p["label"])}</div>', unsafe_allow_html=True)
                    row_cols[2].markdown(f'<div class="painel-row-td">{html.escape(p["number"])}</div>', unsafe_allow_html=True)
                    row_cols[3].markdown(f'<div class="painel-row-td">{html.escape(p.get("responsavel") or "não informado")}</div>', unsafe_allow_html=True)
                    with row_cols[4]:
                        if st.button(
                            ":material/edit:",
                            key=f"edit_processo_{orig_index_by_number[p['number']]}",
                            help="Editar processo",
                        ):
                            show_edit_process_dialog(orig_index_by_number[p["number"]])

        with cad_tab_cnpj:
            st.session_state.setdefault("cnpj_delete_open", False)

            with st.container(key="cnpj_toolbar"):
                if st.button(":material/add:", key="toolbar_add_cnpj", help="Cadastrar CNPJ"):
                    show_add_cnpj_dialog()
                if st.button(":material/delete:", key="toolbar_delete_cnpj", help="Excluir"):
                    st.session_state.cnpj_delete_open = not st.session_state.cnpj_delete_open

            if st.session_state.cnpj_delete_open and st.session_state.monitored_cnpjs:
                cnpj_delete_options = [
                    f"{item['label']} · {format_cnpj_br(item['cnpj'])}" for item in st.session_state.monitored_cnpjs
                ]
                cnpj_del_col, cnpj_confirm_col = st.columns([3, 1])
                with cnpj_del_col:
                    cnpj_delete_choice = st.selectbox(
                        "Selecionar CNPJ para excluir", cnpj_delete_options, label_visibility="collapsed", key="cnpj_delete_select"
                    )
                with cnpj_confirm_col:
                    if st.button("Excluir", key="cnpj_delete_confirm", use_container_width=True):
                        idx = cnpj_delete_options.index(cnpj_delete_choice)
                        st.session_state.monitored_cnpjs.pop(idx)
                        st.session_state.cnpj_delete_open = False
                        st.success("CNPJ removido.")
                        st.rerun()

            filtered_cnpjs = st.session_state.monitored_cnpjs

            if not filtered_cnpjs:
                status("Nenhum CNPJ cadastrado.", "warn")
            else:
                orig_index_by_cnpj = {item["cnpj"]: i for i, item in enumerate(st.session_state.monitored_cnpjs)}
                ratios = [2, 3, 2, 2, 1]
                header_cols = st.columns(ratios)
                for col, label in zip(header_cols, ["CNPJ", "Razão Social", "Cliente", "Responsável", ""]):
                    with col:
                        st.markdown(f'<div class="painel-row-th">{html.escape(label)}</div>', unsafe_allow_html=True)
                for item in filtered_cnpjs:
                    row_cols = st.columns(ratios)
                    row_cols[0].markdown(f'<div class="painel-row-td">{html.escape(format_cnpj_br(item["cnpj"]))}</div>', unsafe_allow_html=True)
                    row_cols[1].markdown(f'<div class="painel-row-td">{html.escape(item["label"])}</div>', unsafe_allow_html=True)
                    row_cols[2].markdown(f'<div class="painel-row-td">{html.escape(item.get("cliente") or "não informado")}</div>', unsafe_allow_html=True)
                    row_cols[3].markdown(f'<div class="painel-row-td">{html.escape(item.get("responsavel") or "não informado")}</div>', unsafe_allow_html=True)
                    with row_cols[4]:
                        if st.button(
                            ":material/edit:",
                            key=f"edit_cnpj_{orig_index_by_cnpj[item['cnpj']]}",
                            help="Editar CNPJ",
                        ):
                            show_edit_cnpj_dialog(orig_index_by_cnpj[item["cnpj"]])

    elif cadastro_sistema == "SEI":
        sei_cad_org_tabs = st.tabs(SEI_ORGAOS)
        for sei_org_tab, sei_org_name in zip(sei_cad_org_tabs, SEI_ORGAOS):
            with sei_org_tab:
                org_processes = [p for p in st.session_state.sei_processes if p["org"] == sei_org_name]
                st.session_state.setdefault(f"sei_delete_open_{sei_org_name}", False)
                st.session_state.setdefault(f"sei_filters_{sei_org_name}", {"tipos": []})

                with st.container(key=f"sei_toolbar_{sei_org_name}"):
                    if st.button(":material/filter_alt:", key=f"toolbar_filter_sei_{sei_org_name}", help="Filtrar"):
                        show_sei_filter_dialog(sei_org_name)
                    if st.button(":material/add:", key=f"toolbar_add_sei_{sei_org_name}", help="Cadastrar processo administrativo"):
                        show_add_sei_process_dialog(sei_org_name)
                    if st.button(":material/delete:", key=f"toolbar_delete_sei_{sei_org_name}", help="Excluir"):
                        st.session_state[f"sei_delete_open_{sei_org_name}"] = not st.session_state[f"sei_delete_open_{sei_org_name}"]

                if st.session_state[f"sei_delete_open_{sei_org_name}"] and org_processes:
                    sei_delete_options = [
                        f"{p['number']} · {p.get('interessado') or 'sem interessado'}" for p in org_processes
                    ]
                    sei_del_col, sei_confirm_col = st.columns([3, 1])
                    with sei_del_col:
                        sei_delete_choice = st.selectbox(
                            "Selecionar processo para excluir",
                            sei_delete_options,
                            label_visibility="collapsed",
                            key=f"sei_delete_select_{sei_org_name}",
                        )
                    with sei_confirm_col:
                        if st.button("Excluir", key=f"sei_delete_confirm_{sei_org_name}", use_container_width=True):
                            proc_to_remove = org_processes[sei_delete_options.index(sei_delete_choice)]
                            st.session_state.sei_processes.remove(proc_to_remove)
                            st.session_state[f"sei_delete_open_{sei_org_name}"] = False
                            st.success("Processo removido.")
                            st.rerun()

                sei_filters = st.session_state[f"sei_filters_{sei_org_name}"]
                filtered_processes = org_processes
                if sei_filters["tipos"]:
                    filtered_processes = [p for p in filtered_processes if p.get("tipo") in sei_filters["tipos"]]

                if not filtered_processes:
                    status(f"Nenhum processo encontrado para {sei_org_name}.")
                else:
                    def _link_status_for_table(proc):
                        if proc.get("forma_acesso") != "Link de acesso":
                            return "Consulta pública"
                        credencial = find_credencial_for_processo(proc["number"])
                        if credencial and credencial.get("link"):
                            return credencial_status(credencial.get("validade"))[0]
                        return "Link não cadastrado"

                    orig_index_by_id = {id(p): i for i, p in enumerate(st.session_state.sei_processes)}
                    ratios = [3, 2, 2, 2, 2, 2, 1]
                    header_cols = st.columns(ratios)
                    for col, label in zip(
                        header_cols,
                        ["Número", "Interessado", "Responsável", "Tipo", "Forma de acesso", "Status do link", ""],
                    ):
                        with col:
                            st.markdown(f'<div class="painel-row-th">{html.escape(label)}</div>', unsafe_allow_html=True)
                    for proc in filtered_processes:
                        row_cols = st.columns(ratios)
                        row_cols[0].markdown(f'<div class="painel-row-td">{html.escape(proc["number"])}</div>', unsafe_allow_html=True)
                        row_cols[1].markdown(f'<div class="painel-row-td">{html.escape(proc.get("interessado") or "não informado")}</div>', unsafe_allow_html=True)
                        row_cols[2].markdown(f'<div class="painel-row-td">{html.escape(proc.get("responsavel") or "não informado")}</div>', unsafe_allow_html=True)
                        row_cols[3].markdown(f'<div class="painel-row-td">{html.escape(proc.get("tipo") or "—")}</div>', unsafe_allow_html=True)
                        row_cols[4].markdown(f'<div class="painel-row-td">{html.escape(proc.get("forma_acesso") or "—")}</div>', unsafe_allow_html=True)
                        row_cols[5].markdown(f'<div class="painel-row-td">{html.escape(_link_status_for_table(proc))}</div>', unsafe_allow_html=True)
                        with row_cols[6]:
                            if st.button(
                                ":material/edit:",
                                key=f"edit_sei_{orig_index_by_id[id(proc)]}",
                                help="Editar processo",
                            ):
                                show_edit_sei_process_dialog(orig_index_by_id[id(proc)])

elif module == "Links e Autenticações":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Links e Autenticações.</h1>'
        '<div class="lede">Controle central dos links de acesso e do prazo de validade de cada credencial '
        'usada pelos conectores (SEI, DET e demais órgãos).</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.session_state.setdefault("cred_filters", {"orgaos": []})

    with st.container(key="cred_toolbar"):
        if st.button(":material/filter_alt:", key="toolbar_filter_cred", help="Filtrar"):
            show_cred_filter_dialog()
        if st.button(":material/add:", key="toolbar_add_cred", help="Cadastrar link de acesso"):
            show_add_credencial_dialog()

    if not st.session_state.credenciais:
        status("Nenhuma credencial cadastrada ainda.", "warn")
    else:
        cred_filters = st.session_state.cred_filters
        filtered_creds = list(enumerate(st.session_state.credenciais))
        if cred_filters["orgaos"]:
            filtered_creds = [(idx, item) for idx, item in filtered_creds if item["org"] in cred_filters["orgaos"]]

        if not filtered_creds:
            status("Nenhuma credencial encontrada para os filtros selecionados.", "warn")
        else:
            cred_table_rows = [
                {
                    "Órgão": item["org"],
                    "Processo vinculado": item.get("processo") or "Geral",
                    "Link": item.get("link") or None,
                    "Validade": item["validade"].strftime("%d/%m/%Y") if item.get("validade") else "—",
                    "Status": credencial_status(item.get("validade"))[0],
                }
                for _, item in filtered_creds
            ]
            cred_selection = st.dataframe(
                cred_table_rows,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="cred_table",
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="Abrir ↗")},
            )
            st.caption("Selecione uma linha para editar a credencial.")
            cred_selected_rows = cred_selection.get("selection", {}).get("rows", []) if cred_selection else []
            if st.button(
                "Editar credencial", key="edit_credencial", disabled=not cred_selected_rows, use_container_width=True
            ):
                show_edit_credencial_dialog(filtered_creds[cred_selected_rows[0]][0])
