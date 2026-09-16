from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
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

# Credenciais OAuth do app Google (Client ID/Secret), cadastradas uma única vez pelo
# desenvolvedor via variável de ambiente ou st.secrets — nunca digitadas na interface.
for _google_env_var in ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"):
    if _google_env_var not in os.environ:
        try:
            if _google_env_var in st.secrets:
                os.environ[_google_env_var] = st.secrets[_google_env_var]
        except Exception:
            pass

from comunica_client import ComunicaClient, ComunicaError  # noqa: E402
from datajud_client import DataJudClient, DataJudError, NumeroProcessoCNJ  # noqa: E402


@st.cache_data
def _load_logo_data_uri(filename: str, _mtime: float) -> str:
    content_type = mimetypes.guess_type(filename)[0] or "image/png"
    encoded = base64.b64encode((CODE_DIR / filename).read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


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

    /* Fixed, scrollable notifications-style alerts card, top-right of the screen.
       Always position:fixed (never part of document flow) so it overlays the page
       instead of shifting the panel's layout, at any viewport width. Discreet: same
       tone as the page background, no border, square corners, like a dropdown menu. */
    /* Streamlit wraps each of these in a "stLayoutWrapper" div that stays in normal flow
       (0 height, but still a flex item) — its parent's flex `gap` still reserves space for
       it, which pushed the page content down when the balloon appeared. display:contents
       removes that wrapper from layout entirely so only our position:fixed boxes remain. */
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-alerts_bell_button"]),
    [data-testid="stLayoutWrapper"]:has(> [class*="st-key-global_alerts_panel"]) {
        display:contents !important;
    }
    /* Bell button: standalone, always visible, fixed top-right — independent of the balloon */
    div[class*="st-key-alerts_bell_button"] {
        position:fixed !important; top:1.3rem; right:2rem; z-index:80; width:auto !important;
    }
    div[class*="st-key-alerts_bell_button"] button {
        width:36px; height:36px; padding:0; display:flex; align-items:center; justify-content:center;
        border-radius:50%; border:none; background:var(--surface); box-shadow:var(--shadow-md);
    }
    div[class*="st-key-alerts_bell_button"] button:hover { background:var(--mint); }
    div[class*="st-key-alerts_bell_button"] button span[data-testid="stIconMaterial"] { color:var(--ink) !important; font-size:18px !important; }
    /* Balloon: only rendered while expanded, floats just below the bell */
    div[class*="st-key-global_alerts_panel"] {
        position:fixed !important; top:3.6rem; right:2rem; width:360px;
        z-index:70; background:var(--paper); border:none; border-radius:0; box-shadow:var(--shadow-md); padding:0;
    }
    /* Fixed max-height with internal scroll so lower links stay reachable */
    div[class*="st-key-alerts_panel_body"] {
        padding:.5rem 0 .3rem; max-height:380px; overflow-y:auto;
    }
    @keyframes alertItemFadeIn { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
    .alert-section-title, .alert-item {
        opacity:0; animation:alertItemFadeIn .3s ease forwards;
    }
    .alert-section-title {
        color:var(--faint); font:700 10px 'DM Mono'; letter-spacing:1px; text-transform:uppercase;
        padding:.6rem 1.1rem .3rem;
    }
    .alert-item {
        display:flex; align-items:baseline; gap:.55rem; padding:.4rem 1.1rem .4rem 1.5rem;
        color:var(--ink); font:13.5px/1.5 Manrope; position:relative;
    }
    .alert-item::before {
        content:""; position:absolute; left:1.15rem; top:.75rem; width:7px; height:7px;
    }
    .alert-item.vencido::before { background:var(--coral); }
    .alert-item.vencendo::before { background:var(--yellow); }
    div[class*="st-key-alerts_panel_footer"] {
        padding:.75rem 1.1rem .85rem; border-top:1px solid var(--line);
    }
    /* "Solicitar novo link" button: discreet, negative/outline scheme using the palette accent */
    div[class*="st-key-alerts_panel_footer"] button {
        background:transparent !important; border:1px solid var(--teal) !important; border-radius:0 !important;
        color:var(--teal-dark) !important; box-shadow:none !important; font-weight:700;
    }
    div[class*="st-key-alerts_panel_footer"] button p { color:inherit !important; }
    div[class*="st-key-alerts_panel_footer"] button:hover:not(:disabled) {
        background:var(--teal) !important; color:#fff !important; transform:none;
    }
    div[class*="st-key-alerts_panel_footer"] button:disabled { opacity:.45; }

    /* Compact send-options row below each (collapsed) process card in "Solicitar novo link" */
    div[class*="st-key-solicitar_send_options_"] { margin:-.4rem 0 .5rem; }
    div[class*="st-key-solicitar_send_options_"] [data-testid="stHorizontalBlock"] { gap:.3rem !important; }
    div[class*="st-key-solicitar_send_options_"] a[data-testid^="stBaseLinkButton"] {
        min-height:0 !important; height:22px !important; padding:0 .35rem !important;
    }
    div[class*="st-key-solicitar_send_options_"] a[data-testid^="stBaseLinkButton"] p { font-size:10px !important; margin:0 !important; }

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
    .status-info { border-radius:8px; padding:.8rem 1.05rem; font:500 12.5px/1.6 Manrope; margin:.3rem 0; color:#1d4e6b; background:#eaf3fa; border:1px solid #c9dced; border-left:3px solid #3f8fcf; }
    .status-info strong { font-weight:700; }
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
                {"Interessado": item["label"], "Número CNJ": item["number"]}
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
                {"Razão Social": item["label"], "CNPJ": format_cnpj_br(item["cnpj"])}
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


def ultima_consulta_label(momento: datetime | None) -> str:
    if not momento:
        return "Nunca consultado"
    dias = (datetime.now() - momento).days
    if dias <= 0:
        return "Hoje"
    return f"Há {dias} dia(s)"


def _ultima_consulta_row_style(row: pd.Series) -> list[str]:
    label = row.get("Última consulta") or ""
    color = ""
    if label == "Hoje":
        color = "background-color:#e5f2ec"
    else:
        match = re.match(r"Há (\d+) dia\(s\)", label)
        if match:
            dias = int(match.group(1))
            color = "background-color:#fdf6e3" if dias <= 5 else "background-color:#fbe4de"
    return [color if col == "Última consulta" else "" for col in row.index]


RESPONSAVEL_CORES = {
    "Sibylla Naoum": "#ece1f7",
    "Gabriella": "#dff1e8",
    "Ana Laura": "#fde8d3",
}


def _cor_responsavel(valor: str) -> str:
    cor = RESPONSAVEL_CORES.get(valor)
    return f"background-color:{cor};" if cor else ""


def estilizar_responsavel(df: pd.DataFrame):
    """Devolve um Styler que colore a coluna 'Responsável' com uma cor fixa por pessoa, se a coluna existir."""
    styler = df.style
    if "Responsável" in df.columns:
        styler = styler.map(_cor_responsavel, subset=["Responsável"])
    return styler


def credencial_status(validade):
    if not validade:
        return ("Sem prazo de validade informado", "neutral")
    dias = (validade - date.today()).days
    if dias < 0:
        return (f"Vencido há {abs(dias)} dia(s)", "warn")
    if dias <= 15:
        return (f"Vence em {dias} dia(s)", "warn")
    return (f"Válido até {validade.strftime('%d/%m/%Y')}", "ok")


def credencial_link_label(item: dict) -> str:
    nome = (item.get("nome") or "").strip()
    if nome:
        label = nome
    else:
        link = item.get("link") or ""
        label = link if len(link) <= 60 else f"{link[:57]}..."
    validade = item.get("validade")
    return f"{label} (até {validade.strftime('%d/%m/%Y')})" if validade else label


def credenciais_com_link_do_orgao(org: str) -> list[dict]:
    return [c for c in st.session_state.credenciais if c["org"] == org and c.get("link")]


SEI_LINK_STATUS_CATEGORIES = ["Ativo", "Em vencimento", "Vencido"]


def sei_link_status(proc) -> tuple[str, str | None]:
    """Retorna (rótulo exibido, categoria) para o status do link de acesso do processo SEI.

    Categoria é uma de SEI_LINK_STATUS_CATEGORIES, ou None quando não se aplica
    (consulta pública ou link não cadastrado)."""
    if proc.get("forma_acesso") != "Restrito":
        return "Consulta pública", None
    credencial = find_credencial_for_processo(proc["number"])
    if credencial and credencial.get("link"):
        validade = credencial.get("validade")
        if not validade:
            return "Ativo (sem prazo informado)", "Ativo"
        dias = (validade - date.today()).days
        if dias < 0:
            return f"Vencido há {abs(dias)} dia(s)", "Vencido"
        if dias <= 10:
            return f"Vence em {dias} dia(s)", "Em vencimento"
        return f"Válido até {validade.strftime('%d/%m/%Y')}", "Ativo"
    if proc.get("link"):
        return "Ativo (sem prazo informado)", "Ativo"
    return "Link não cadastrado", None


def sei_consultar_link(proc: dict) -> str | None:
    """Retorna o link a abrir para consultar o processo: o link de acesso cadastrado
    diretamente no processo, o link da credencial vinculada, ou o portal de consulta
    pública do órgão quando a forma de acesso for consulta pública."""
    if proc.get("link"):
        return proc["link"]
    if proc.get("forma_acesso") == "Consulta pública":
        return SEI_CONSULTA_PUBLICA_URLS.get(proc["org"])
    return (find_credencial_for_processo(proc["number"]) or {}).get("link")


def credencial_alert_category(item: dict) -> str | None:
    """Retorna 'Vencido', 'Em vencimento' (≤10 dias) ou None para uma credencial/link."""
    validade = item.get("validade")
    if not validade:
        return None
    dias = (validade - date.today()).days
    if dias < 0:
        return "Vencido"
    if dias <= 10:
        return "Em vencimento"
    return None


def collect_link_alerts() -> list[dict]:
    alerts = []
    for idx, item in enumerate(st.session_state.credenciais):
        categoria = credencial_alert_category(item)
        if categoria:
            alerts.append({"index": idx, "item": item, "categoria": categoria, "dias": (item["validade"] - date.today()).days})
    return alerts


def _prazo_text(alert: dict) -> str:
    dias = alert["dias"]
    return f"vencido há {abs(dias)} dia(s)" if dias < 0 else f"vence em {dias} dia(s)"


def render_email_template(alerts: list[dict]) -> tuple[str, str]:
    """Renderiza o e-mail padrão para um único processo/link (um alerta)."""
    profile = st.session_state.firm_profile
    template = st.session_state.email_template
    primary = alerts[0]["item"] if alerts else {}
    context = {
        "usuario": profile.get("usuario") or "",
        "escritorio": profile.get("nome") or "",
        "processo": primary.get("processo") or "Geral",
        "orgao": primary.get("org") or "",
        "link": primary.get("link") or "",
        "validade": primary["validade"].strftime("%d/%m/%Y") if primary.get("validade") else "",
        "status": _prazo_text(alerts[0]) if alerts else "",
    }

    def _fill(text: str) -> str:
        for key, value in context.items():
            text = text.replace("{" + key + "}", value)
        return text

    return _fill(template["assunto"]), _fill(template["corpo"])


def collect_alert_recipients(alerts: list[dict]) -> list[str]:
    recipients: list[str] = []
    for alert in alerts:
        for email in alert["item"].get("emails") or []:
            email = email.strip()
            if email and email not in recipients:
                recipients.append(email)
    return recipients


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",  # leitura dos e-mails de push do TCU
]
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def is_gmail_address(email: str | None) -> bool:
    if not email or "@" not in email:
        return False
    return email.strip().lower().rsplit("@", 1)[-1] in GMAIL_DOMAINS


def _google_oauth_client_config() -> dict | None:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def conectar_conta_google() -> tuple[bool, str]:
    """Abre o navegador para o login/consentimento do Google e guarda as credenciais na sessão."""
    client_config = _google_oauth_client_config()
    if not client_config:
        return False, "Informe o Client ID e o Client Secret do Google Cloud antes de conectar."
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return False, "Bibliotecas do Google não instaladas. Rode: pip install -r requirements.txt"
    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as exc:
        return False, f"Falha na autenticação com o Google: {exc}"
    st.session_state.email_sender_config["oauth_account"] = creds.to_json()
    return True, "Conta Google conectada."


def desconectar_conta_google() -> None:
    st.session_state.email_sender_config["oauth_account"] = None


def _enviar_email_oauth_google(remetente: str, destinatarios: list[str], assunto: str, corpo: str) -> tuple[bool, str]:
    token_json = st.session_state.email_sender_config.get("oauth_account")
    if not token_json:
        return False, "Conecte sua conta Google na página E-mails antes de enviar."
    if not destinatarios:
        return False, "Nenhum destinatário informado."
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        return False, "Bibliotecas do Google não instaladas. Rode: pip install -r requirements.txt"

    creds = Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)
    try:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state.email_sender_config["oauth_account"] = creds.to_json()

        msg = MIMEText(corpo, "plain", "utf-8")
        msg["Subject"] = assunto
        msg["From"] = remetente
        msg["To"] = ", ".join(destinatarios)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        service = build("gmail", "v1", credentials=creds)
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, f"E-mail enviado para {len(destinatarios)} destinatário(s)."
    except Exception as exc:
        return False, f"Falha ao enviar e-mail: {exc}"


def email_sender_ready() -> bool:
    """Indica se dá para enviar automaticamente agora (só para remetentes do Gmail, conectados)."""
    remetente = st.session_state.firm_profile.get("email", "")
    if not is_gmail_address(remetente):
        return False
    return bool(st.session_state.email_sender_config.get("oauth_account"))


def enviar_email(destinatarios: list[str], assunto: str, corpo: str) -> tuple[bool, str]:
    """Ponto único de envio automático — usa a conta Google conectada (só remetentes @gmail.com)."""
    remetente = st.session_state.firm_profile.get("email", "")
    return _enviar_email_oauth_google(remetente, destinatarios, assunto, corpo)


def gmail_compose_url(destinatarios: list[str], assunto: str, corpo: str) -> str:
    params = {"view": "cm", "fs": "1", "to": ", ".join(destinatarios), "su": assunto, "body": corpo}
    return "https://mail.google.com/mail/?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def outlook_compose_url(destinatarios: list[str], assunto: str, corpo: str) -> str:
    params = {"to": ";".join(destinatarios), "subject": assunto, "body": corpo}
    return "https://outlook.office.com/mail/deeplink/compose?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def mailto_compose_url(destinatarios: list[str], assunto: str, corpo: str) -> str:
    """Abre o cliente de e-mail padrão do sistema (ex.: Outlook instalado)."""
    to = urllib.parse.quote(",".join(destinatarios))
    query = urllib.parse.urlencode({"subject": assunto, "body": corpo}, quote_via=urllib.parse.quote)
    return f"mailto:{to}?{query}"


def google_account_connected() -> bool:
    return bool(st.session_state.email_sender_config.get("oauth_account"))


TCU_PROCESSO_REGEX = re.compile(r"^\s*(\d{3})\.?(\d{3})/(\d{4})-(\d)\s*$")
TCU_PUSH_ASSUNTO_REGEX = re.compile(r"\[TCU\]\s*Acompanhamento Processual\s*-\s*Processo\s*(.+)", re.IGNORECASE)
TCU_PUSH_CADASTRO_URL = (
    "https://contas.tcu.gov.br/jurisSessoes/Web/Juris/ConsultaProcessoPush/ConsultarProcessoPush.faces"
)


def normalizar_numero_tcu(numero: str) -> str:
    """Valida e normaliza um número de processo TCU (formato NNN.NNN/AAAA-D)."""
    match = TCU_PROCESSO_REGEX.match(numero or "")
    if not match:
        raise ValueError("Número de processo TCU inválido. Use o formato NNN.NNN/AAAA-D (ex.: 012.345/2024-3).")
    p1, p2, ano, dv = match.groups()
    return f"{p1}.{p2}/{ano}-{dv}"


def tcu_numero_digits(numero: str) -> str:
    return re.sub(r"\D", "", numero or "")


def tcu_pesquisa_publica_url(numero: str) -> str:
    """Página de documentos do processo na busca pública do TCU, já aberta no processo certo.

    Formato confirmado a partir de uma URL real capturada pelo usuário ao navegar até um
    processo específico em pesquisa.apps.tcu.gov.br. O número do processo vai com a barra
    escapada (%2F) e depois o trecho inteiro é escapado de novo (por isso o %25 duplicado),
    como um segmento de rota do Angular; os demais segmentos (filtro em branco e ordenação)
    são fixos, iguais aos que o próprio site usa por padrão. Não exige login nem credencial.
    """
    numero_barra_escapada = urllib.parse.quote(numero, safe="")
    numero_duplo_escapado = urllib.parse.quote(numero_barra_escapada, safe="")
    return (
        "https://pesquisa.apps.tcu.gov.br/documento/processo/"
        f"{numero_duplo_escapado}/%2520/"
        "DTAUTUACAOORDENACAO%2520desc%252C%2520NUMEROCOMZEROS%2520desc/0"
    )


def tcu_conecta_url(numero: str) -> str:
    """Página do processo no Conecta TCU (histórico completo), já aberta no processo certo.

    Formato confirmado pelo usuário: digitando o número na busca da página inicial do
    usuário credenciado, o Conecta TCU redireciona para /tvp-por-numero/{número só dígitos}.
    Diferente da busca pública, essa página exige estar logado no Conecta TCU (xCPF/senha) —
    sem sessão ativa, o TCU redireciona primeiro para a tela de login antes de mostrar o processo.
    """
    return f"https://conecta-tcu.apps.tcu.gov.br/tvp-por-numero/{tcu_numero_digits(numero)}"


def parse_tcu_push_email(assunto: str, corpo: str) -> dict | None:
    """Extrai os dados estruturados do e-mail de 'Acompanhamento processual (Push)' do TCU.

    Retorna None quando o e-mail não bate com o formato esperado, em vez de levantar erro —
    a sincronização deve ignorar e-mails inesperados, não quebrar por causa deles.
    """
    assunto_match = TCU_PUSH_ASSUNTO_REGEX.search(assunto or "")
    if not assunto_match:
        return None

    def _campo(rotulo: str) -> str:
        # Ancorado no início da linha: o texto de introdução do e-mail também usa a palavra
        # "movimentação" numa frase solta, então sem isso o regex pegaria a frase errada.
        campo_match = re.search(rf"^{rotulo}\s*:\s*(.+)$", corpo or "", re.IGNORECASE | re.MULTILINE)
        return campo_match.group(1).strip() if campo_match else ""

    numero_processo = _campo(r"Processo") or assunto_match.group(1).strip()
    numero_processo = re.sub(r"^TC\s*", "", numero_processo, flags=re.IGNORECASE).strip()
    movimentacao = _campo(r"Movimenta[cç][aã]o")
    if not numero_processo or not movimentacao:
        return None

    data_match = re.search(
        r"^Data do evento\s*:\s*(\d{2}/\d{2}/\d{4})\s*(?:às|as)\s*(\d{2}:\d{2})",
        corpo or "", re.IGNORECASE | re.MULTILINE,
    )
    data_evento = None
    if data_match:
        try:
            data_evento = datetime.strptime(f"{data_match.group(1)} {data_match.group(2)}", "%d/%m/%Y %H:%M").date()
        except ValueError:
            data_evento = None

    return {
        "numero_processo": numero_processo,
        "relator": _campo(r"Redator/Relator"),
        "interessados": _campo(r"Interessado\(s\)/Respons[aá]vel\(is\)"),
        "data_evento": data_evento,
        "descricao": movimentacao,
    }


def _extrair_assunto_corpo_gmail(mensagem_gmail: dict) -> tuple[str, str]:
    payload = mensagem_gmail.get("payload", {})
    headers = payload.get("headers", [])
    assunto = next((h["value"] for h in headers if h.get("name", "").lower() == "subject"), "")

    def _achar_texto_plano(part: dict) -> str | None:
        body_data = part.get("body", {}).get("data")
        if part.get("mimeType") == "text/plain" and body_data:
            padded = body_data + "=" * (-len(body_data) % 4)
            return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        for sub_part in part.get("parts", []) or []:
            texto = _achar_texto_plano(sub_part)
            if texto:
                return texto
        return None

    return assunto, _achar_texto_plano(payload) or ""


def sincronizar_tcu_push() -> tuple[int, list[str]]:
    """Lê a caixa do Gmail conectado em busca de e-mails de push do TCU e atualiza as
    movimentações dos processos cadastrados. Retorna (quantidade de movimentações novas, avisos)."""
    if not google_account_connected():
        return 0, ["Conecte sua conta Google em Autenticações para sincronizar automaticamente."]
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        return 0, ["Bibliotecas do Google não instaladas. Rode: pip install -r requirements.txt"]

    token_json = st.session_state.email_sender_config["oauth_account"]
    creds = Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)
    try:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state.email_sender_config["oauth_account"] = creds.to_json()
        service = build("gmail", "v1", credentials=creds)
        resultado_busca = service.users().messages().list(
            userId="me", q='subject:"[TCU] Acompanhamento Processual"', maxResults=50
        ).execute()
        mensagens = resultado_busca.get("messages", [])
    except Exception as exc:
        return 0, [f"Falha ao consultar o Gmail: {exc}"]

    processados = st.session_state.setdefault("tcu_push_processed_ids", set())
    novos = 0
    avisos: list[str] = []

    for msg_ref in mensagens:
        msg_id = msg_ref["id"]
        if msg_id in processados:
            continue
        try:
            mensagem_completa = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        except Exception as exc:
            avisos.append(f"Falha ao ler um e-mail do TCU: {exc}")
            continue

        processados.add(msg_id)
        assunto, corpo = _extrair_assunto_corpo_gmail(mensagem_completa)
        dados = parse_tcu_push_email(assunto, corpo)
        if not dados:
            continue

        numero_digitos = tcu_numero_digits(dados["numero_processo"])
        processo = next(
            (p for p in st.session_state.tcu_processes if tcu_numero_digits(p["number"]) == numero_digitos), None
        )
        if not processo:
            avisos.append(f"Recebido e-mail do processo TC {dados['numero_processo']}, que não está cadastrado.")
            continue

        ja_existe = any(
            m.get("data") == dados["data_evento"] and m.get("descricao") == dados["descricao"]
            for m in processo["movements"]
        )
        if not ja_existe:
            processo["movements"].append({
                "data": dados["data_evento"],
                "descricao": dados["descricao"],
                "relator": dados["relator"],
                "interessados": dados["interessados"],
            })
            processo["last_query"] = datetime.now()
            novos += 1

    return novos, avisos


def movimentacoes_tcu_processo(processo: dict) -> list[dict]:
    """Movimentações capturadas via Push (e-mail de acompanhamento processual do TCU)."""
    return [
        {
            "Data": m.get("data"),
            "Descrição": m.get("descricao"),
            "Relator": m.get("relator") or "não informado",
        }
        for m in processo.get("movements", [])
    ]


CONECTA_TCU_HISTORICO_REGEX = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})\s*-\s*(.+?)"
    r"(?=\n\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s*-|\Z)",
    re.DOTALL,
)


def parse_conecta_tcu_historico(texto: str) -> list[dict]:
    """Extrai (data, descrição) das linhas coladas da aba HISTÓRICO do Conecta-TCU.

    O formato de cada linha é "DD/MM/AAAA HH:MM:SS - descrição"; usa lookahead para a
    próxima data em vez de dividir por linha, então descrições que quebraram em mais de
    uma linha ao colar continuam sendo tratadas como uma única movimentação.
    """
    entradas = []
    for match in CONECTA_TCU_HISTORICO_REGEX.finditer(texto or ""):
        data_str, hora_str, descricao_bruta = match.groups()
        try:
            data = datetime.strptime(f"{data_str} {hora_str}", "%d/%m/%Y %H:%M:%S").date()
        except ValueError:
            continue
        descricao = " ".join(descricao_bruta.split())
        if descricao:
            entradas.append({"data": data, "descricao": descricao})
    return entradas


def importar_historico_conecta_tcu(processo: dict, texto: str) -> int:
    """Importa (com deduplicação) as movimentações coladas do Conecta-TCU. Retorna quantas eram novas."""
    entradas = parse_conecta_tcu_historico(texto)
    existentes = processo.setdefault("movements_conecta", [])
    novos = 0
    for entrada in entradas:
        ja_existe = any(
            m.get("data") == entrada["data"] and m.get("descricao") == entrada["descricao"] for m in existentes
        )
        if not ja_existe:
            existentes.append(entrada)
            novos += 1
    existentes.sort(key=lambda m: m.get("data") or date.min, reverse=True)
    if novos:
        processo["last_query"] = datetime.now()
    return novos


def movimentacoes_tcu_conecta(processo: dict) -> list[dict]:
    """Movimentações importadas manualmente do histórico completo do Conecta-TCU."""
    return [
        {"Data": m.get("data"), "Descrição": m.get("descricao")}
        for m in processo.get("movements_conecta", [])
    ]


def ultima_movimentacao_tcu(processo: dict):
    """Última movimentação conhecida, considerando as duas fontes (Push e Conecta-TCU)."""
    movimentos = movimentacoes_tcu_processo(processo) + movimentacoes_tcu_conecta(processo)
    if not movimentos:
        return None, None
    ultima = max(movimentos, key=lambda m: m.get("Data") or date.min)
    return ultima.get("Data"), ultima.get("Descrição")


@st.dialog("Solicitar novo link de acesso", width="large")
def show_solicitar_link_dialog() -> None:
    alerts = collect_link_alerts()
    if not alerts:
        status("Nenhum link vencido ou a vencer no momento.", "neutral")
        return

    st.caption(
        "Um e-mail é preparado separadamente para cada processo vencido ou a vencer (até 10 dias), com os "
        "destinatários associados àquele link."
    )

    remetente = st.session_state.firm_profile.get("email", "")
    usa_gmail_oauth = is_gmail_address(remetente)
    remetente_pronto = email_sender_ready()

    if usa_gmail_oauth:
        if not remetente_pronto:
            status(
                "Conecte sua conta Google na página E-mails para habilitar o envio automático. Enquanto isso, "
                "use as opções abaixo para enviar manualmente.",
                "warn",
            )
    else:
        status(
            f"O e-mail cadastrado ({html.escape(remetente) if remetente else 'não informado'}) não é do Gmail. "
            "Abra cada solicitação no Gmail, Outlook ou no seu app de e-mail padrão para enviar manualmente.",
            "neutral",
        )

    pode_enviar = False
    for alert in sorted(alerts, key=lambda a: (a["categoria"] != "Vencido", a["dias"])):
        item = alert["item"]
        processo = item.get("processo") or "Geral"
        assunto, corpo = render_email_template([alert])
        destinatarios = collect_alert_recipients([alert])
        if destinatarios:
            pode_enviar = True

        dias = alert["dias"]
        prazo_label = f"vencido há {abs(dias)}d" if alert["categoria"] == "Vencido" else f"vence em {dias}d"
        with st.expander(f"{item['org']} · Processo {processo} · {prazo_label}", expanded=False):
            st.markdown('<div class="eyebrow">E-MAIL PADRÃO</div>', unsafe_allow_html=True)
            st.text_input("Assunto", value=assunto, disabled=True, key=f"solicitar_assunto_{alert['index']}")
            st.text_area("Corpo", value=corpo, disabled=True, height=180, key=f"solicitar_corpo_{alert['index']}")
            st.markdown('<div class="eyebrow">DESTINATÁRIOS</div>', unsafe_allow_html=True)
            if not destinatarios:
                status("Nenhum e-mail associado a este link. Associe e-mails na página E-mails.", "warn")
            else:
                st.write(", ".join(destinatarios))

        if destinatarios and not remetente_pronto:
            with st.container(key=f"solicitar_send_options_{alert['index']}"):
                padrao_col, gmail_col, outlook_col = st.columns(3)
                with padrao_col:
                    st.link_button(
                        "App padrão",
                        mailto_compose_url(destinatarios, assunto, corpo),
                        use_container_width=True,
                        help="Abre o cliente de e-mail padrão do seu computador (ex.: Outlook instalado).",
                    )
                with gmail_col:
                    st.link_button(
                        "Gmail", gmail_compose_url(destinatarios, assunto, corpo), use_container_width=True
                    )
                with outlook_col:
                    st.link_button(
                        "Outlook (web)", outlook_compose_url(destinatarios, assunto, corpo), use_container_width=True
                    )

    if usa_gmail_oauth and st.button(
        "Confirmar e enviar",
        type="primary",
        use_container_width=True,
        disabled=not pode_enviar or not remetente_pronto,
        key="solicitar_confirmar_envio",
    ):
        enviados, falhas, sem_destinatario = 0, [], []
        for alert in alerts:
            item = alert["item"]
            processo = item.get("processo") or "Geral"
            destinatarios = collect_alert_recipients([alert])
            if not destinatarios:
                sem_destinatario.append(processo)
                continue
            assunto, corpo = render_email_template([alert])
            ok, msg = enviar_email(destinatarios, assunto, corpo)
            if ok:
                enviados += 1
            else:
                falhas.append(f"{processo}: {msg}")

        if enviados:
            st.success(f"{enviados} e-mail(s) enviado(s), um por processo.")
        if sem_destinatario:
            st.warning("Sem e-mail associado, não enviado: " + ", ".join(sem_destinatario))
        if falhas:
            st.error("Falha ao enviar: " + "; ".join(falhas))


@st.fragment
def render_alerts_panel() -> None:
    """Sino independente, fixo no canto superior direito; o balão de notificações só
    aparece (sobreposto, sem alterar o layout da página) enquanto estiver expandido.
    Roda como fragment para que abrir/fechar o balão não recarregue o resto da página."""
    alerts = collect_link_alerts()
    if not alerts:
        return

    expanded = st.session_state.get("notifications_enabled", True)

    with st.container(key="alerts_bell_button"):
        bell_icon = ":material/notifications:" if expanded else ":material/notifications_off:"
        if st.button(
            bell_icon,
            key="toggle_notifications_button",
            help="Ocultar notificações" if expanded else "Ver notificações",
        ):
            st.session_state.notifications_enabled = not expanded
            st.rerun(scope="fragment")

    if not expanded:
        return

    with st.container(key="global_alerts_panel"):
        with st.container(key="alerts_panel_body"):
            vencidos_alerts = sorted(
                (a for a in alerts if a["categoria"] == "Vencido"), key=lambda a: a["dias"]
            )
            vencendo_alerts = sorted(
                (a for a in alerts if a["categoria"] == "Em vencimento"), key=lambda a: a["dias"]
            )

            _fade_step = 0

            def _fade_delay_style() -> str:
                nonlocal _fade_step
                delay = min(_fade_step * 0.05, 0.4)
                _fade_step += 1
                return f' style="animation-delay:{delay:.2f}s"'

            if vencidos_alerts:
                st.markdown(
                    f'<div class="alert-section-title"{_fade_delay_style()}>Links vencidos</div>', unsafe_allow_html=True
                )
                for alert in vencidos_alerts:
                    processo = html.escape(alert["item"].get("processo") or "Geral")
                    dias = abs(alert["dias"])
                    st.markdown(
                        f'<div class="alert-item vencido"{_fade_delay_style()}>Processo {processo} '
                        f'(há {dias} dia{"s" if dias != 1 else ""})</div>',
                        unsafe_allow_html=True,
                    )

            if vencendo_alerts:
                st.markdown(
                    f'<div class="alert-section-title"{_fade_delay_style()}>Links a vencer</div>', unsafe_allow_html=True
                )
                for alert in vencendo_alerts:
                    processo = html.escape(alert["item"].get("processo") or "Geral")
                    dias = alert["dias"]
                    st.markdown(
                        f'<div class="alert-item vencendo"{_fade_delay_style()}>Processo {processo} '
                        f'(daqui a {dias} dia{"s" if dias != 1 else ""})</div>',
                        unsafe_allow_html=True,
                    )

        with st.container(key="alerts_panel_footer"):
            if st.button(
                "Solicitar novo link",
                key="alertas_solicitar_link",
                use_container_width=True,
                help="Prepara um e-mail de solicitação de renovação para cada processo vencido ou a vencer.",
            ):
                show_solicitar_link_dialog()


@st.dialog("Cadastrar link de acesso")
def show_add_credencial_dialog() -> None:
    sei_process_options = ["(nenhum processo vinculado)"] + [p["number"] for p in st.session_state.sei_processes]
    with st.form("credencial_form", clear_on_submit=True):
        cred_nome = st.text_input("Identificador", placeholder="Ex.: Link licitação 06/2026", key="cred_nome")
        cred_org = st.selectbox("Órgão", st.session_state.sei_orgaos + ["Outro"], key="cred_org")
        cred_processo = st.selectbox("Processo vinculado", sei_process_options, key="cred_processo")
        cred_link = st.text_input("Link de acesso", placeholder="https://sei.orgao.gov.br/... (ainda não disponível)", key="cred_link")
        cred_validade = st.date_input("Prazo de validade", value=None, key="cred_validade")
        cred_add = st.form_submit_button("Cadastrar credencial", use_container_width=True)
    if cred_add:
        if not cred_link.strip():
            st.warning("Informe o link de acesso.")
        else:
            st.session_state.credenciais.append({
                "nome": cred_nome.strip(),
                "org": cred_org,
                "processo": None if cred_processo == "(nenhum processo vinculado)" else cred_processo,
                "link": cred_link.strip(),
                "validade": cred_validade,
                "emails": [],
            })
            st.success("Credencial cadastrada.")
            st.rerun()


@st.dialog("Editar link de acesso")
def show_edit_credencial_dialog(index: int) -> None:
    item = st.session_state.credenciais[index]
    sei_process_options = ["(nenhum processo vinculado)"] + [p["number"] for p in st.session_state.sei_processes]
    org_options = st.session_state.sei_orgaos + ["Outro"]
    current_org = item.get("org")
    org_index = org_options.index(current_org) if current_org in org_options else len(org_options) - 1
    current_processo = item.get("processo") or "(nenhum processo vinculado)"
    processo_index = sei_process_options.index(current_processo) if current_processo in sei_process_options else 0

    with st.form("credencial_edit_form"):
        cred_nome = st.text_input(
            "Identificador", value=item.get("nome") or "", placeholder="Ex.: Link licitação 06/2026", key="cred_edit_nome"
        )
        cred_org = st.selectbox("Órgão", org_options, index=org_index, key="cred_edit_org")
        cred_processo = st.selectbox("Processo vinculado", sei_process_options, index=processo_index, key="cred_edit_processo")
        cred_link = st.text_input("Link de acesso", value=item.get("link") or "", key="cred_edit_link")
        cred_validade = st.date_input("Prazo de validade", value=item.get("validade"), key="cred_edit_validade")
        cred_emails = st.text_area(
            "E-mail(s) remetente para solicitação de renovação (separados por vírgula)",
            value=", ".join(item.get("emails") or []),
            placeholder="ex.: diad@inas.df.gov.br, contato@orgao.gov.br",
            key="cred_edit_emails",
        )
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
                "nome": cred_nome.strip(),
                "org": cred_org,
                "processo": None if cred_processo == "(nenhum processo vinculado)" else cred_processo,
                "link": cred_link.strip(),
                "validade": cred_validade,
                "emails": [e.strip() for e in cred_emails.split(",") if e.strip()],
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


def _sync_auth_env_var(item: dict) -> None:
    """Repassa o valor da autenticação para os.environ quando ela alimenta uma variável
    de ambiente usada pelos conectores (hoje, só a chave do DataJud)."""
    env_var = item.get("env_var")
    if env_var and item.get("valor"):
        os.environ[env_var] = item["valor"]


@st.dialog("Cadastrar autenticação")
def show_add_auth_dialog() -> None:
    with st.form("auth_form", clear_on_submit=True):
        auth_chave = st.text_input(
            "Chave (identificador)", placeholder="Ex.: SEI, GOV.br, DataJud...", key="auth_chave"
        )
        auth_sistema = st.text_input(
            "Sistema/Órgão", placeholder="Ex.: SEI do Ministério do Esporte", key="auth_sistema"
        )
        auth_usuario = st.text_input("Usuário/Login", placeholder="Opcional", key="auth_usuario")
        auth_valor = st.text_input(
            "Senha ou chave de API", type="password", placeholder="Opcional", key="auth_valor"
        )
        auth_obs = st.text_input("Observação", placeholder="Opcional", key="auth_obs")
        auth_add = st.form_submit_button("Cadastrar", use_container_width=True)
    if auth_add:
        if not auth_chave.strip():
            st.warning("Informe a chave (identificador).")
        else:
            st.session_state.auth_credenciais.append({
                "chave": auth_chave.strip(),
                "sistema": auth_sistema.strip(),
                "usuario": auth_usuario.strip(),
                "valor": auth_valor,
                "observacao": auth_obs.strip(),
                "env_var": None,
            })
            st.success("Autenticação cadastrada.")
            st.rerun()


@st.dialog("Editar autenticação")
def show_edit_auth_dialog(index: int) -> None:
    item = st.session_state.auth_credenciais[index]
    with st.form("auth_edit_form"):
        auth_chave = st.text_input("Chave (identificador)", value=item.get("chave") or "", key="auth_edit_chave")
        auth_sistema = st.text_input("Sistema/Órgão", value=item.get("sistema") or "", key="auth_edit_sistema")
        auth_usuario = st.text_input("Usuário/Login", value=item.get("usuario") or "", key="auth_edit_usuario")
        auth_valor = st.text_input(
            "Senha ou chave de API", value=item.get("valor") or "", type="password", key="auth_edit_valor"
        )
        auth_obs = st.text_input("Observação", value=item.get("observacao") or "", key="auth_edit_obs")
        save_col, remove_col = st.columns(2)
        with save_col:
            auth_save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            auth_remove = st.form_submit_button("Remover autenticação", use_container_width=True)

    if auth_save:
        if not auth_chave.strip():
            st.warning("Informe a chave (identificador).")
        else:
            updated = {
                "chave": auth_chave.strip(),
                "sistema": auth_sistema.strip(),
                "usuario": auth_usuario.strip(),
                "valor": auth_valor,
                "observacao": auth_obs.strip(),
                "env_var": item.get("env_var"),
            }
            _sync_auth_env_var(updated)
            st.session_state.auth_credenciais[index] = updated
            st.success("Autenticação atualizada.")
            st.rerun()
    if auth_remove:
        st.session_state.auth_credenciais.pop(index)
        st.success("Autenticação removida.")
        st.rerun()


DJEN_COUNT_CAP = 10000


def format_djen_count(count) -> str:
    if count == DJEN_COUNT_CAP:
        return "10000+ (limite da API)"
    return str(count)


def format_cnpj_br(digits: str) -> str:
    if len(digits) != 14:
        return digits
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def mask_secret(value: str | None) -> str:
    if not value:
        return "Não configurada"
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 8}{value[-4:]}"


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
    ultima_atualizacao=None,
    consultar_link: str | None = None,
    consultar_proc: dict | None = None,
    consultar_action=None,
    refresh=None,
    sources: dict[str, list[dict]] | None = None,
    default_source: str | None = None,
    unavailable_sources: dict[str, str] | None = None,
    source_widgets: dict[str, Callable[[], None]] | None = None,
    sincronizar_action=None,
    sincronizar_disabled: bool = False,
    sincronizar_help: str | None = None,
    busca_publica_url: str | None = None,
    notice: Callable[[], None] | None = None,
) -> None:
    st.markdown(f'<div class="eyebrow">{html.escape(titulo)}</div>', unsafe_allow_html=True)

    if notice is not None:
        notice()

    if consultar_action is not None:
        if st.button("Consultar", type="primary", use_container_width=True, key="mov_dialog_consultar_action"):
            with st.spinner("Consultando..."):
                consultar_action()
    elif consultar_proc is not None:
        if sincronizar_action is not None:
            consultar_col, sincronizar_col = st.columns([3, 2])
        else:
            consultar_col, sincronizar_col = st.container(), None
        with consultar_col:
            st.link_button(
                "Consultar",
                consultar_link or "#",
                type="primary",
                use_container_width=True,
                disabled=not consultar_link,
                key="mov_dialog_consultar",
            )
        if sincronizar_col is not None:
            with sincronizar_col:
                if st.button(
                    "Sincronizar",
                    use_container_width=True,
                    key="mov_dialog_sincronizar",
                    disabled=sincronizar_disabled,
                    help=sincronizar_help,
                ):
                    with st.spinner("Sincronizando..."):
                        sync_novos, sync_avisos = sincronizar_action()
                    if sync_novos:
                        st.success(f"{sync_novos} nova(s) movimentação(ões) importada(s).")
                    elif not sync_avisos:
                        st.info("Nenhuma movimentação nova encontrada.")
                    for sync_aviso in sync_avisos:
                        st.warning(sync_aviso)
        if not consultar_link:
            status("Link de acesso não cadastrado para este processo.", "warn")
        if busca_publica_url:
            st.caption(
                "Exige login no Conecta TCU (histórico completo). Sem login? "
                f"[Busca pública, sem login ↗]({busca_publica_url})"
            )

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
            if source_widgets and chosen_source in source_widgets:
                source_widgets[chosen_source]()
                if refresh is not None:
                    sources = refresh().get("sources", sources)
            _render_movimentacoes_rows(sources.get(chosen_source, []))
    else:
        _render_movimentacoes_rows(rows or [])


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


DJEN_ORGAOS_EXEMPLO = [
    "1ª Vara Cível", "2ª Vara Cível", "Vara de Fazenda Pública", "1ª Turma Recursal", "Secretaria Judicial",
]
DJEN_TIPOS_COMUNICACAO_EXEMPLO = ["Intimação", "Citação", "Publicação de Ato Ordinatório"]
DJEN_TIPOS_DOCUMENTO_EXEMPLO = ["Despacho", "Decisão Interlocutória", "Sentença", "Certidão de Publicação"]
DJEN_LINK_EXEMPLO = "https://comunica.pje.jus.br/consulta"

DJEN_INDISPONIVEL_TITULO = "Consulta em tempo real ao DJEN indisponível neste ambiente."
DJEN_INDISPONIVEL_TEXTO = (
    "A API pública do DJEN (Diário de Justiça Eletrônico Nacional) restringe requisições a endereços IP "
    "localizados no Brasil. Este protótipo está hospedado fora do país, então a consulta automática não é "
    "concluída aqui — o mesmo código volta a funcionar normalmente ao publicar em um servidor com IP "
    "brasileiro (ou atrás de um proxy/túnel brasileiro). Os registros abaixo são <strong>ilustrativos</strong>, "
    "exibidos apenas para demonstrar como as publicações reais apareceriam nesta tela."
)


def render_djen_indisponivel_notice() -> None:
    st.markdown(
        f'<div class="status-info"><strong>{DJEN_INDISPONIVEL_TITULO}</strong><br/>{DJEN_INDISPONIVEL_TEXTO}</div>',
        unsafe_allow_html=True,
    )


def _gerar_djen_items_exemplo(
    numero_processo: Optional[str] = None, quantidade: int = 4
) -> list[dict]:
    """Publicações ilustrativas no formato do DJEN, usadas quando a API real está indisponível
    neste ambiente (hospedagem fora do Brasil, fora do alcance de IP aceito pela API pública)."""
    hoje = date.today()
    itens = []
    for i in range(quantidade):
        dias_atras = 3 + i * 6
        itens.append(
            {
                "data_disponibilizacao": (hoje - timedelta(days=dias_atras)).isoformat(),
                "nomeOrgao": DJEN_ORGAOS_EXEMPLO[i % len(DJEN_ORGAOS_EXEMPLO)],
                "tipoComunicacao": DJEN_TIPOS_COMUNICACAO_EXEMPLO[i % len(DJEN_TIPOS_COMUNICACAO_EXEMPLO)],
                "tipoDocumento": DJEN_TIPOS_DOCUMENTO_EXEMPLO[i % len(DJEN_TIPOS_DOCUMENTO_EXEMPLO)],
                "link": DJEN_LINK_EXEMPLO,
                "numeroprocessocommascara": numero_processo,
                "numero_processo": numero_processo,
            }
        )
    return itens


def _gerar_djen_response_exemplo(numero_processo: Optional[str] = None, quantidade: int = 4) -> dict:
    itens = _gerar_djen_items_exemplo(numero_processo=numero_processo, quantidade=quantidade)
    return {"items": itens, "count": len(itens), "_mock": True}


DATAJUD_MOVIMENTOS_EXEMPLO = [
    "Distribuição", "Juntada de Petição", "Conclusão para decisão", "Decisão", "Expedição de intimação",
]
DATAJUD_CLASSE_EXEMPLO = "Procedimento Comum Cível"
DATAJUD_ASSUNTO_EXEMPLO = "Responsabilidade Civil"
DATAJUD_SISTEMA_EXEMPLO = "PJe"

DATAJUD_INDISPONIVEL_TITULO = "Consulta em tempo real ao DataJud indisponível neste ambiente."
DATAJUD_INDISPONIVEL_TEXTO = (
    "A API pública do DataJud (CNJ) não respondeu a tempo a partir deste ambiente — a mesma família de "
    "restrição de rede que afeta o DJEN: como é uma API oficial brasileira, ela pode limitar, atrasar ou "
    "recusar requisições vindas de fora do Brasil. Este protótipo está hospedado fora do país, então a "
    "consulta automática pode falhar ou expirar aqui — o mesmo código volta a funcionar normalmente ao "
    "publicar em um servidor com IP brasileiro. As movimentações abaixo são <strong>ilustrativas</strong>, "
    "exibidas apenas para demonstrar como o histórico real apareceria nesta tela."
)


def render_datajud_indisponivel_notice() -> None:
    st.markdown(
        f'<div class="status-info"><strong>{DATAJUD_INDISPONIVEL_TITULO}</strong><br/>{DATAJUD_INDISPONIVEL_TEXTO}</div>',
        unsafe_allow_html=True,
    )


def _render_dje_dialog_notices(numero_processo: str) -> None:
    """Mostra os avisos de dados ilustrativos (DJEN e/ou DataJud) para o diálogo de histórico do Painel Geral."""
    if (st.session_state.djen_results.get(numero_processo) or {}).get("_mock"):
        render_djen_indisponivel_notice()
    if (st.session_state.datajud_results.get(numero_processo) or {}).get("_mock"):
        render_datajud_indisponivel_notice()


def _gerar_datajud_result_exemplo(numero_processo: str, quantidade: int = 5) -> dict:
    """Movimentações e dados de capa ilustrativos no formato do DataJud, usados quando a API real está
    indisponível neste ambiente (hospedagem fora do Brasil, fora do alcance de IP aceito pela API pública,
    ou tempo de resposta esgotado)."""
    hoje = date.today()
    movimentos = []
    for i in range(quantidade):
        dias_atras = (quantidade - i) * 12
        movimentos.append(
            {
                "numero_processo": numero_processo,
                "data_hora": (hoje - timedelta(days=dias_atras)).isoformat(),
                "nome": DATAJUD_MOVIMENTOS_EXEMPLO[i % len(DATAJUD_MOVIMENTOS_EXEMPLO)],
                "complementos": None,
                "bruto": {"orgaoJulgador": {"nome": DJEN_ORGAOS_EXEMPLO[i % len(DJEN_ORGAOS_EXEMPLO)]}},
            }
        )
    source = {
        "classe": {"nome": DATAJUD_CLASSE_EXEMPLO},
        "assuntos": [{"nome": DATAJUD_ASSUNTO_EXEMPLO}],
        "grau": "1º Grau",
        "sistema": {"nome": DATAJUD_SISTEMA_EXEMPLO},
        "dataAjuizamento": (hoje - timedelta(days=quantidade * 12 + 30)).isoformat(),
    }
    return {"response": None, "source": source, "movements": movimentos, "_mock": True}


def _fetch_dje_processo_dados(parsed: NumeroProcessoCNJ) -> dict:
    """Só faz as chamadas de rede (sem tocar em st.session_state) — pode rodar em outra thread."""
    process_number = parsed.bruto
    dados: dict = {"djen_response": None, "datajud_result": None, "erros": []}
    try:
        dados["djen_response"] = ComunicaClient().buscar_todos(numero_processo=process_number)
    except ComunicaError:
        dados["djen_response"] = _gerar_djen_response_exemplo(numero_processo=process_number)
    try:
        client = DataJudClient()
        response = client.buscar_por_numero_processo(parsed)
        hits = response.get("hits", {}).get("hits", [])
        source = hits[0].get("_source", {}) if hits else {}
        movements = client.extrair_movimentacoes(response)
        dados["datajud_result"] = {"response": response, "source": source, "movements": movements}
    except DataJudError:
        dados["datajud_result"] = _gerar_datajud_result_exemplo(process_number)
    return dados


def _aplicar_dje_processo_dados(process_number: str, dados: dict) -> tuple[bool, list[str]]:
    """Grava em st.session_state o resultado de `_fetch_dje_processo_dados` — só na thread principal."""
    obteve_dados = False
    if dados["djen_response"] is not None:
        st.session_state.djen_results[process_number] = dados["djen_response"]
        obteve_dados = True
    if dados["datajud_result"] is not None:
        st.session_state.datajud_results[process_number] = dados["datajud_result"]
        obteve_dados = True
    if obteve_dados:
        st.session_state.query_timestamps[process_number] = datetime.now()
    return obteve_dados, dados["erros"]


def consultar_dje_processo(process_number: str, *, silent: bool = False) -> tuple[bool, list[str]]:
    try:
        parsed = NumeroProcessoCNJ.parse(process_number)
    except ValueError:
        parsed = None
    if not parsed:
        msg = "Informe um número CNJ válido."
        if not silent:
            st.error(msg)
        return False, [msg]
    dados = _fetch_dje_processo_dados(parsed)
    obteve_dados, erros = _aplicar_dje_processo_dados(process_number, dados)
    if not silent:
        for erro in erros:
            st.error(erro)
    return obteve_dados, erros


DJE_CNPJ_NOT_IMPLEMENTED_MSG = (
    "A API própria do DJe ainda não tem integração implementada, então não é possível "
    "exibir uma tabela de movimentações por processo aqui. Use a aba \"Diário (DJEN)\" "
    "para ver as publicações já disponíveis, ou consulte cada processo individualmente "
    "na aba Processos."
)


DJEN_PROCESSOS_EXEMPLO_CNPJ = [
    "0012045-88.2025.8.26.0100",
    "0803312-40.2024.8.19.0001",
    "1004521-19.2026.4.01.3400",
]


def _gerar_djen_response_exemplo_cnpj(quantidade: int = 3) -> dict:
    """Como `_gerar_djen_response_exemplo`, mas com um processo fictício diferente por item —
    a busca por CNPJ/razão social costuma reunir publicações de mais de um processo."""
    hoje = date.today()
    itens = []
    for i in range(quantidade):
        dias_atras = 4 + i * 9
        numero = DJEN_PROCESSOS_EXEMPLO_CNPJ[i % len(DJEN_PROCESSOS_EXEMPLO_CNPJ)]
        itens.append(
            {
                "data_disponibilizacao": (hoje - timedelta(days=dias_atras)).isoformat(),
                "nomeOrgao": DJEN_ORGAOS_EXEMPLO[i % len(DJEN_ORGAOS_EXEMPLO)],
                "tipoComunicacao": DJEN_TIPOS_COMUNICACAO_EXEMPLO[i % len(DJEN_TIPOS_COMUNICACAO_EXEMPLO)],
                "tipoDocumento": DJEN_TIPOS_DOCUMENTO_EXEMPLO[i % len(DJEN_TIPOS_DOCUMENTO_EXEMPLO)],
                "link": DJEN_LINK_EXEMPLO,
                "numeroprocessocommascara": numero,
                "numero_processo": numero,
            }
        )
    return {"items": itens, "count": len(itens), "_mock": True}


def _fetch_dje_cnpj_dados(cnpj_item: dict) -> dict:
    """Só faz a chamada de rede (sem tocar em st.session_state) — pode rodar em outra thread."""
    dados: dict = {"djen_response": None, "erro": None}
    try:
        dados["djen_response"] = ComunicaClient().buscar_todos(nome_parte=cnpj_item["label"])
    except ComunicaError:
        dados["djen_response"] = _gerar_djen_response_exemplo_cnpj()
    return dados


def _aplicar_dje_cnpj_dados(cnpj_key: str, dados: dict) -> tuple[bool, list[str]]:
    """Grava em st.session_state o resultado de `_fetch_dje_cnpj_dados` — só na thread principal."""
    if dados["djen_response"] is not None:
        st.session_state.djen_cnpj_results[cnpj_key] = dados["djen_response"]
        st.session_state.cnpj_query_timestamps[cnpj_key] = datetime.now()
        return True, []
    return False, [dados["erro"]] if dados["erro"] else []


def consultar_dje_cnpj(cnpj_item: dict, *, silent: bool = False) -> tuple[bool, list[str]]:
    cnpj_key = cnpj_item["cnpj"]
    dados = _fetch_dje_cnpj_dados(cnpj_item)
    obteve_dados, erros = _aplicar_dje_cnpj_dados(cnpj_key, dados)
    if not silent:
        for erro in erros:
            st.error(erro)
    return obteve_dados, erros


if "processes" not in st.session_state:
    st.session_state.processes = [
        {"number": "0001149-33.2026.8.26.0127", "label": "H Plus Administração e Hotelaria Ltda", "responsavel": "Sibylla Naoum"},
        {"number": "5000145-27.2016.8.13.0016", "label": "Hotel Naoum Brasília Ltda", "responsavel": "Gabriella"},
        {"number": "0802205-61.2024.8.19.0021", "label": "Express Brasília Hospedagem e Turismo S/A", "responsavel": "Ana Laura"},
        {"number": "1031108-73.2025.4.01.3400", "label": "Construtora Planalto Ltda", "responsavel": "Sibylla Naoum"},
    ]
if "monitored_cnpjs" not in st.session_state:
    st.session_state.monitored_cnpjs = [
        {
            "cnpj": "01652106000132",
            "label": "Hotel Naoum Brasília Ltda",
            "interessado": "Diretoria Financeira",
            "responsavel": "Gabriella",
        },
        {
            "cnpj": "05217384000151",
            "label": "H Plus Administração e Hotelaria Ltda",
            "interessado": "Departamento Jurídico",
            "responsavel": "Ana Laura",
        },
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
            "interessado": "Construtora Planalto Ltda",
            "responsavel": "Sibylla Naoum",
            "sistema_origem": "SEI",
            "forma_acesso": "Restrito",
            "link": "",
            "movements": [],
            "last_query": None,
        },
        {
            "number": "58000-00012345/2025-71",
            "org": "Ministério do Esporte",
            "interessado": "Confederação Brasileira de Handebol",
            "responsavel": "Gabriella",
            "sistema_origem": "SEI",
            "forma_acesso": "Restrito",
            "link": "",
            "movements": [],
            "last_query": None,
        },
        {
            "number": "04001-00007300/2025-88",
            "org": "Governo do Distrito Federal",
            "interessado": "Consórcio Vias DF",
            "responsavel": "Ana Laura",
            "sistema_origem": "SEI",
            "forma_acesso": "Restrito",
            "link": "",
            "movements": [],
            "last_query": None,
        },
        {
            "number": "58000-00012999/2025-05",
            "org": "Ministério do Esporte",
            "interessado": "Federação de Vôlei de Praia do DF",
            "responsavel": "Sibylla Naoum",
            "sistema_origem": "SEI",
            "forma_acesso": "Restrito",
            "link": "",
            "movements": [],
            "last_query": None,
        },
        {
            "number": "04001-00007555/2025-20",
            "org": "Governo do Distrito Federal",
            "interessado": "Construtora Planalto Ltda",
            "responsavel": "Gabriella",
            "sistema_origem": "SEI",
            "forma_acesso": "Restrito",
            "link": "",
            "movements": [],
            "last_query": None,
        },
        {
            "number": "58000-00013500/2025-40",
            "org": "Ministério do Esporte",
            "interessado": "Confederação Brasileira de Atletismo",
            "responsavel": "Ana Laura",
            "sistema_origem": "SEI",
            "forma_acesso": "Restrito",
            "link": "",
            "movements": [],
            "last_query": None,
        },
        {
            "number": "00220-00006906/2024-56",
            "org": "Governo do Distrito Federal",
            "interessado": "Consórcio Vias DF",
            "responsavel": "Sibylla Naoum",
            "sistema_origem": "SEI",
            "forma_acesso": "Consulta pública",
            "link": "",
            "movements": [],
            "last_query": None,
        },
    ]
if "tcu_processes" not in st.session_state:
    st.session_state.tcu_processes = [
        {
            "number": "010.139/2026-5",
            "tipo": "Prestação de contas",
            "interessado": "Confederação Brasileira de Ginástica",
            "responsavel": "Gabriella",
            "conecta_url": "",
            "movements": [],
            "movements_conecta": [],
            "last_query": None,
        },
        {
            "number": "006.971/2026-1",
            "tipo": "Convênio",
            "interessado": "Consórcio Vias DF",
            "responsavel": "Ana Laura",
            "conecta_url": "",
            "movements": [],
            "movements_conecta": [],
            "last_query": None,
        },
        {
            "number": "003.060/2026-8",
            "tipo": "Sancionador",
            "interessado": "Construtora Planalto Ltda",
            "responsavel": "Sibylla Naoum",
            "conecta_url": "",
            "movements": [],
            "movements_conecta": [],
            "last_query": None,
        },
    ]
if "tcu_push_processed_ids" not in st.session_state:
    st.session_state.tcu_push_processed_ids = set()
if "credenciais" not in st.session_state:
    st.session_state.credenciais = [
        {
            "nome": "Link GDF · processo 6993",
            "org": "Governo do Distrito Federal",
            "processo": "04001-00006993/2025-40",
            "link": "http://sei.df.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=2442842&infra_hash=f930b708871a3a2490e540fef130a96a",
            "validade": date(2026, 9, 4),
            "emails": ["diad@inas.df.gov.br"],
        },
        {
            "nome": "Link Min. Esporte · processo 12345",
            "org": "Ministério do Esporte",
            "processo": "58000-00012345/2025-71",
            "link": "https://sei.esporte.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=999001&infra_hash=exemplo1",
            "validade": date(2027, 3, 15),
            "emails": ["camargosadvogados@gmail.com"],
        },
        {
            "nome": "Link GDF · processo 7300",
            "org": "Governo do Distrito Federal",
            "processo": "04001-00007300/2025-88",
            "link": "http://sei.df.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=999002&infra_hash=exemplo2",
            "validade": date(2026, 12, 1),
            "emails": ["camargosadvogados@gmail.com"],
        },
        {
            "nome": "Link Min. Esporte · processo 12999",
            "org": "Ministério do Esporte",
            "processo": "58000-00012999/2025-05",
            "link": "https://sei.esporte.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=999003&infra_hash=exemplo3",
            "validade": date.today() - timedelta(days=15),
            "emails": ["camargosadvogados@gmail.com"],
        },
        {
            "nome": "Link GDF · processo 7555",
            "org": "Governo do Distrito Federal",
            "processo": "04001-00007555/2025-20",
            "link": "http://sei.df.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=999004&infra_hash=exemplo4",
            "validade": date.today() - timedelta(days=40),
            "emails": ["camargosadvogados@gmail.com"],
        },
        {
            "nome": "Link Min. Esporte · processo 13500",
            "org": "Ministério do Esporte",
            "processo": "58000-00013500/2025-40",
            "link": "https://sei.esporte.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=999005&infra_hash=exemplo5",
            "validade": date.today() + timedelta(days=180),
            "emails": ["camargosadvogados@gmail.com"],
        },
    ]
if "email_sender_config" not in st.session_state:
    st.session_state.email_sender_config = {
        "oauth_account": None,  # credenciais OAuth (JSON) depois de conectar a conta Google
    }
if "notifications_enabled" not in st.session_state:
    st.session_state.notifications_enabled = True
if "email_template" not in st.session_state:
    st.session_state.email_template = {
        "assunto": "Solicitação de renovação de link de acesso – Processo {processo}",
        "corpo": (
            "Prezados,\n\n"
            "O link de acesso ao processo {processo} está com status: {status}.\n\n"
            "Link atual: {link}\n\n"
            "Solicitamos a gentileza de providenciar a emissão de um novo link de acesso.\n\n"
            "Atenciosamente,\n"
            "{usuario}\n"
            "{escritorio}"
        ),
    }

if "auth_credenciais" not in st.session_state:
    st.session_state.auth_credenciais = [
        {
            "chave": "E-mail",
            "sistema": "E-mail do usuário",
            "usuario": st.session_state.get("firm_profile", {}).get("email") or "",
            "valor": "",
            "observacao": "Login e senha da conta de e-mail do dia a dia (quando não for Gmail com login por Google).",
            "env_var": None,
        },
        {
            "chave": "SEI",
            "sistema": "SEI",
            "usuario": "",
            "valor": "",
            "observacao": "Login e senha de acesso restrito ao SEI de cada órgão.",
            "env_var": None,
        },
        {
            "chave": "GOV.br",
            "sistema": "GOV.br",
            "usuario": "",
            "valor": "",
            "observacao": "Login único do governo federal, usado por sistemas como o Conecta TCU.",
            "env_var": None,
        },
        {
            "chave": "DataJud",
            "sistema": "DataJud (CNJ)",
            "usuario": "",
            "valor": os.environ.get("DATAJUD_API_KEY", ""),
            "observacao": "Chave de API para consulta de movimentações processuais no DataJud.",
            "env_var": "DATAJUD_API_KEY",
        },
        {
            "chave": "DJEN",
            "sistema": "DJEN",
            "usuario": "",
            "valor": "",
            "observacao": "Chave de API do Diário de Justiça Eletrônico Nacional, se vier a ser exigida.",
            "env_var": None,
        },
        {
            "chave": "DJe",
            "sistema": "DJe",
            "usuario": "",
            "valor": "",
            "observacao": "Ainda não disponível — a API própria do DJe não tem integração implementada.",
            "env_var": None,
        },
        {
            "chave": "TCU",
            "sistema": "TCU · Conecta TCU",
            "usuario": "",
            "valor": "",
            "observacao": "Usuário e senha (login GOV.br) do Conecta TCU, usado para consultar o histórico completo.",
            "env_var": None,
        },
    ]

SEI_ORGAOS_DEFAULT = ["Ministério do Esporte", "Governo do Distrito Federal"]
if "sei_orgaos" not in st.session_state:
    st.session_state.sei_orgaos = list(SEI_ORGAOS_DEFAULT)
SEI_FORMAS_ACESSO = ["Restrito", "Consulta pública"]
SEI_CONSULTA_PUBLICA_URLS = {
    "Governo do Distrito Federal": (
        "https://sei.df.gov.br/sei/modulos/pesquisa/md_pesq_processo_pesquisar.php"
        "?acao_externa=protocolo_pesquisar&acao_origem_externa=protocolo_pesquisar&id_orgao_acesso_externo=0"
    ),
}
TCU_TIPOS = ["Sancionador", "Prestação de contas", "Convênio", "Outro"]


@st.dialog("Cadastrar processo")
def show_add_process_dialog() -> None:
    with st.form("process_form", clear_on_submit=True):
        new_process_label = st.text_input("Interessado", placeholder="Ex.: Federação X")
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
        cnpj_label = st.text_input("Razão Social", placeholder="Empresa monitorada")
        cnpj_interessado = st.text_input("Interessado", placeholder="Ex.: Federação X")
        add_cnpj = st.form_submit_button("Adicionar CNPJ", use_container_width=True)
    if add_cnpj:
        digits = "".join(char for char in cnpj if char.isdigit())
        if len(digits) != 14 or not cnpj_label.strip():
            st.warning("Informe um CNPJ válido e a Razão Social.")
        elif any(item["cnpj"] == digits for item in st.session_state.monitored_cnpjs):
            st.warning("Esse CNPJ já está monitorado.")
        else:
            st.session_state.monitored_cnpjs.append(
                {"cnpj": digits, "label": cnpj_label.strip(), "interessado": cnpj_interessado.strip()}
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
                    {"cnpj": digits, "label": raw_label or "Empresa importada", "interessado": "", "responsavel": ""}
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
        edit_label = st.text_input("Interessado", value=item["label"])
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
        edit_label = st.text_input("Razão Social", value=item["label"])
        edit_interessado = st.text_input("Interessado", value=item.get("interessado") or "")
        edit_responsavel = st.text_input("Responsável", value=item.get("responsavel") or "")
        save_col, remove_col = st.columns(2)
        with save_col:
            save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            remove = st.form_submit_button("Remover CNPJ", use_container_width=True)
    if save:
        digits = "".join(char for char in edit_cnpj if char.isdigit())
        if len(digits) != 14 or not edit_label.strip():
            st.warning("Informe um CNPJ válido e a Razão Social.")
        elif any(i != index and other["cnpj"] == digits for i, other in enumerate(st.session_state.monitored_cnpjs)):
            st.warning("Esse CNPJ já está monitorado.")
        else:
            st.session_state.monitored_cnpjs[index] = {
                "cnpj": digits,
                "label": edit_label.strip(),
                "interessado": edit_interessado.strip(),
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
def show_add_sei_process_dialog(sei_org_name: str | None = None) -> None:
    key_suffix = sei_org_name or "todos"

    if sei_org_name is None:
        sei_org_selected = st.selectbox("Órgão", st.session_state.sei_orgaos, key=f"sei_org_{key_suffix}")
    else:
        sei_org_selected = sei_org_name

    sei_forma_acesso = st.selectbox("Forma de acesso", SEI_FORMAS_ACESSO, key=f"sei_forma_{key_suffix}")

    org_credenciais: list[dict] = []
    link_labels: list[str] = []
    sei_link_text = ""
    if sei_forma_acesso == "Restrito":
        org_credenciais = credenciais_com_link_do_orgao(sei_org_selected)
        link_labels = ["(nenhum)"] + [credencial_link_label(c) for c in org_credenciais]
        link_select_col, link_add_col = st.columns([5, 1])
        with link_select_col:
            sei_link_choice = st.selectbox("Link de acesso", link_labels, key=f"sei_link_choice_{key_suffix}")
        with link_add_col:
            st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
            if st.button("+", key=f"sei_link_add_{key_suffix}", help="Cadastrar link de acesso em Links e E-mails", use_container_width=True):
                st.session_state.active_module = "Links e E-mails"
                st.rerun()
        if not org_credenciais:
            st.caption(f"Nenhum link cadastrado para {sei_org_selected} ainda. Use o botão \"+\" para cadastrar um em Links e E-mails.")
    else:
        sei_link_text = st.text_input(
            "Link de acesso", placeholder="https://sei.orgao.gov.br/... (opcional)", key=f"sei_link_text_{key_suffix}"
        )

    with st.form(f"sei_form_{key_suffix}", clear_on_submit=True):
        sei_number = st.text_input("Número do processo", placeholder="Ex.: 58000.012345/2026-11", key=f"sei_number_{key_suffix}")
        sei_interessado = st.text_input("Interessado", placeholder="Ex.: Federação X", key=f"sei_interessado_{key_suffix}")
        sei_responsavel = st.text_input("Responsável", placeholder="Ex.: Advogado(a) responsável", key=f"sei_responsavel_{key_suffix}")
        sei_sistema_origem = st.text_input("Sistema de origem", value="SEI", placeholder="Ex.: SEI", key=f"sei_sistema_{key_suffix}")
        sei_add = st.form_submit_button("Cadastrar processo", use_container_width=True)
    if sei_add:
        if not sei_number.strip():
            st.warning("Informe o número do processo.")
        elif any(p["number"] == sei_number.strip() and p["org"] == sei_org_selected for p in st.session_state.sei_processes):
            st.warning("Esse processo já está cadastrado para este órgão.")
        else:
            if sei_forma_acesso == "Restrito":
                link_choice_index = link_labels.index(sei_link_choice)
                resolved_link = "" if link_choice_index == 0 else org_credenciais[link_choice_index - 1]["link"]
            else:
                resolved_link = sei_link_text.strip()
            st.session_state.sei_processes.append({
                "number": sei_number.strip(),
                "org": sei_org_selected,
                "interessado": sei_interessado.strip(),
                "responsavel": sei_responsavel.strip(),
                "sistema_origem": sei_sistema_origem.strip() or "SEI",
                "forma_acesso": sei_forma_acesso,
                "link": resolved_link,
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
    filters = st.session_state.setdefault(state_key, {"formas_acesso": []})
    selected_formas = st.multiselect(
        "Forma de acesso",
        SEI_FORMAS_ACESSO,
        default=[f for f in filters["formas_acesso"] if f in SEI_FORMAS_ACESSO],
        key=f"sei_filter_formas_input_{sei_org_name}",
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key=f"sei_filter_apply_{sei_org_name}", type="primary", use_container_width=True):
            st.session_state[state_key] = {"formas_acesso": selected_formas}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key=f"sei_filter_clear_{sei_org_name}", use_container_width=True):
            st.session_state[state_key] = {"formas_acesso": []}
            st.rerun()


@st.dialog("Adicionar órgão")
def show_add_sei_orgao_dialog() -> None:
    with st.form("sei_add_orgao_form", clear_on_submit=True):
        new_sei_orgao = st.text_input(
            "Nome do órgão", placeholder="Ex.: Ministério da Justiça", key="sei_new_orgao_input"
        )
        add_sei_orgao_submit = st.form_submit_button("Adicionar órgão", use_container_width=True)
    if add_sei_orgao_submit:
        new_orgao_name = new_sei_orgao.strip()
        if not new_orgao_name:
            st.warning("Informe o nome do órgão.")
        elif new_orgao_name in st.session_state.sei_orgaos:
            st.warning("Esse órgão já está cadastrado.")
        else:
            st.session_state.sei_orgaos.append(new_orgao_name)
            st.success("Órgão adicionado.")
            st.rerun()


@st.dialog("Filtrar processos")
def show_sei_cadastro_todos_filter_dialog() -> None:
    filters = st.session_state.setdefault("sei_filters_todos", {"formas_acesso": [], "orgaos": []})
    orgao_options = sorted({p["org"] for p in st.session_state.sei_processes})
    selected_orgaos = st.multiselect(
        "Órgão", orgao_options, default=[o for o in filters["orgaos"] if o in orgao_options], key="sei_cadastro_todos_filter_orgaos_input"
    )
    selected_formas = st.multiselect(
        "Forma de acesso",
        SEI_FORMAS_ACESSO,
        default=[f for f in filters["formas_acesso"] if f in SEI_FORMAS_ACESSO],
        key="sei_cadastro_todos_filter_formas_input",
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="sei_cadastro_todos_filter_apply", type="primary", use_container_width=True):
            st.session_state.sei_filters_todos = {"formas_acesso": selected_formas, "orgaos": selected_orgaos}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="sei_cadastro_todos_filter_clear", use_container_width=True):
            st.session_state.sei_filters_todos = {"formas_acesso": [], "orgaos": []}
            st.rerun()


@st.dialog("Editar processo administrativo")
def show_edit_sei_process_dialog(index: int) -> None:
    item = st.session_state.sei_processes[index]

    edit_org_options = st.session_state.sei_orgaos
    edit_org = st.selectbox(
        "Órgão",
        edit_org_options,
        index=edit_org_options.index(item["org"]) if item["org"] in edit_org_options else 0,
        key=f"sei_edit_org_{index}",
    )

    edit_forma_acesso = st.selectbox(
        "Forma de acesso",
        SEI_FORMAS_ACESSO,
        index=SEI_FORMAS_ACESSO.index(item["forma_acesso"]) if item.get("forma_acesso") in SEI_FORMAS_ACESSO else 0,
        key=f"sei_edit_forma_{index}",
    )

    edit_org_credenciais: list[dict] = []
    edit_link_labels: list[str] = []
    edit_link_text = ""
    if edit_forma_acesso == "Restrito":
        edit_org_credenciais = credenciais_com_link_do_orgao(edit_org)
        edit_link_labels = ["(nenhum)"] + [credencial_link_label(c) for c in edit_org_credenciais]
        current_link = item.get("link") or ""
        edit_link_links = [c["link"] for c in edit_org_credenciais]
        edit_link_default_index = edit_link_links.index(current_link) + 1 if current_link in edit_link_links else 0

        edit_link_select_col, edit_link_add_col = st.columns([5, 1])
        with edit_link_select_col:
            edit_link_choice = st.selectbox(
                "Link de acesso", edit_link_labels, index=edit_link_default_index, key=f"sei_edit_link_choice_{index}"
            )
        with edit_link_add_col:
            st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
            if st.button(
                "+", key=f"sei_edit_link_add_{index}", help="Cadastrar link de acesso em Links e E-mails", use_container_width=True
            ):
                st.session_state.active_module = "Links e E-mails"
                st.rerun()
        if not edit_org_credenciais:
            st.caption(f"Nenhum link cadastrado para {edit_org} ainda. Use o botão \"+\" para cadastrar um em Links e E-mails.")
    else:
        edit_link_text = st.text_input(
            "Link de acesso", value=item.get("link") or "", placeholder="https://sei.orgao.gov.br/... (opcional)",
            key=f"sei_edit_link_text_{index}",
        )

    with st.form("sei_edit_form"):
        edit_number = st.text_input("Número do processo", value=item["number"])
        edit_interessado = st.text_input("Interessado", value=item.get("interessado") or "")
        edit_responsavel = st.text_input("Responsável", value=item.get("responsavel") or "")
        edit_sistema_origem = st.text_input("Sistema de origem", value=item.get("sistema_origem") or "SEI")
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
            if edit_forma_acesso == "Restrito":
                edit_link_choice_index = edit_link_labels.index(edit_link_choice)
                edit_resolved_link = (
                    "" if edit_link_choice_index == 0 else edit_org_credenciais[edit_link_choice_index - 1]["link"]
                )
            else:
                edit_resolved_link = edit_link_text.strip()
            st.session_state.sei_processes[index] = {
                **item,
                "number": edit_number.strip(),
                "org": edit_org,
                "interessado": edit_interessado.strip(),
                "responsavel": edit_responsavel.strip(),
                "sistema_origem": edit_sistema_origem.strip() or "SEI",
                "forma_acesso": edit_forma_acesso,
                "link": edit_resolved_link,
            }
            st.success("Processo atualizado.")
            st.rerun()
    if remove:
        st.session_state.sei_processes.pop(index)
        st.success("Processo removido.")
        st.rerun()


@st.dialog("Filtrar processos TCU")
def show_tcu_filter_dialog() -> None:
    filters = st.session_state.setdefault("tcu_filters", {"tipos": []})
    tipo_options = sorted({p.get("tipo") for p in st.session_state.tcu_processes if p.get("tipo")})
    selected_tipos = st.multiselect(
        "Tipo", tipo_options, default=[t for t in filters["tipos"] if t in tipo_options], key="tcu_filter_tipos_input"
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="tcu_filter_apply", type="primary", use_container_width=True):
            st.session_state.tcu_filters = {"tipos": selected_tipos}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="tcu_filter_clear", use_container_width=True):
            st.session_state.tcu_filters = {"tipos": []}
            st.rerun()


@st.dialog("Filtrar processos")
def show_painel_proc_filter_dialog() -> None:
    filters = st.session_state.setdefault("painel_proc_filters", {"sistemas": [], "responsaveis": []})
    sistema_options = ["DJe", "SEI", "TCU"]
    selected_sistemas = st.multiselect(
        "Sistema",
        sistema_options,
        default=[s for s in filters["sistemas"] if s in sistema_options],
        key="painel_proc_filter_sistemas_input",
    )
    responsavel_options = sorted({
        item.get("responsavel") or "não informado"
        for item in st.session_state.processes + st.session_state.sei_processes + st.session_state.tcu_processes
    })
    selected_responsaveis = st.multiselect(
        "Responsável",
        responsavel_options,
        default=[r for r in filters["responsaveis"] if r in responsavel_options],
        key="painel_proc_filter_responsaveis_input",
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="painel_proc_filter_apply", type="primary", use_container_width=True):
            st.session_state.painel_proc_filters = {"sistemas": selected_sistemas, "responsaveis": selected_responsaveis}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="painel_proc_filter_clear", use_container_width=True):
            st.session_state.painel_proc_filters = {"sistemas": [], "responsaveis": []}
            st.rerun()


@st.dialog("Filtrar CNPJs")
def show_painel_cnpj_filter_dialog() -> None:
    filters = st.session_state.setdefault("painel_cnpj_filters", {"responsaveis": []})
    responsavel_options = sorted({item.get("responsavel") or "não informado" for item in st.session_state.monitored_cnpjs})
    selected_responsaveis = st.multiselect(
        "Responsável",
        responsavel_options,
        default=[r for r in filters["responsaveis"] if r in responsavel_options],
        key="painel_cnpj_filter_responsaveis_input",
    )
    apply_col, clear_col = st.columns(2)
    with apply_col:
        if st.button("Aplicar filtros", key="painel_cnpj_filter_apply", type="primary", use_container_width=True):
            st.session_state.painel_cnpj_filters = {"responsaveis": selected_responsaveis}
            st.rerun()
    with clear_col:
        if st.button("Limpar filtros", key="painel_cnpj_filter_clear", use_container_width=True):
            st.session_state.painel_cnpj_filters = {"responsaveis": []}
            st.rerun()


DJE_BULK_CONSULTA_CONCORRENCIA = 5  # nº de consultas simultâneas — bem abaixo do limite de 120/min do DataJud


@st.dialog("Consultar todos os processos (DJe)")
def show_painel_consultar_todos_proc_dialog(numeros: list[str]) -> None:
    total = len(numeros)
    resultado_key = "painel_consultar_todos_proc_resultado"

    def _mostrar_resultado(sucesso: int, erros: list[tuple[str, str]]) -> None:
        if sucesso:
            st.success(f"{sucesso} de {total} processo(s) consultado(s) com sucesso.")
        for numero, motivo in erros:
            st.warning(f"{numero}: {motivo}")
        if st.button("Fechar", use_container_width=True, key="fechar_consultar_todos_proc"):
            st.session_state.pop(resultado_key, None)
            st.rerun()

    resultado = st.session_state.get(resultado_key)
    if resultado is not None:
        _mostrar_resultado(*resultado)
        return

    st.markdown(
        f"Isso vai consultar **{total} processo(s)** no DataJud e no DJEN, até "
        f"{DJE_BULK_CONSULTA_CONCORRENCIA} de cada vez (dentro do limite de 120 requisições/min do "
        "DataJud). Pode levar alguns minutos, dependendo da resposta das APIs."
    )
    if st.button("Consultar todos", type="primary", use_container_width=True, key="confirmar_consultar_todos_proc"):
        progress = st.progress(0.0)
        status_placeholder = st.empty()
        erros: list[tuple[str, str]] = []
        sucesso = 0
        concluidos = 0
        parsed_por_numero: dict[str, NumeroProcessoCNJ] = {}
        for numero in numeros:
            try:
                parsed_por_numero[numero] = NumeroProcessoCNJ.parse(numero)
            except ValueError:
                erros.append((numero, "Número CNJ inválido."))
                concluidos += 1

        # Só a busca (sem tocar em st.session_state) roda nas threads; a gravação do
        # resultado acontece aqui embaixo, sempre na thread principal.
        with ThreadPoolExecutor(max_workers=DJE_BULK_CONSULTA_CONCORRENCIA) as executor:
            futures = {
                executor.submit(_fetch_dje_processo_dados, parsed): numero
                for numero, parsed in parsed_por_numero.items()
            }
            for future in as_completed(futures):
                numero = futures[future]
                dados = future.result()
                obteve_dados, mensagens_erro = _aplicar_dje_processo_dados(numero, dados)
                if obteve_dados:
                    sucesso += 1
                if mensagens_erro:
                    erros.append((numero, "; ".join(mensagens_erro)))
                concluidos += 1
                status_placeholder.caption(f"Consultando... {concluidos} de {total} concluído(s).")
                progress.progress(concluidos / total)
        status_placeholder.empty()
        st.session_state[resultado_key] = (sucesso, erros)
        _mostrar_resultado(sucesso, erros)


@st.dialog("Consultar todos os CNPJs (DJe)")
def show_painel_consultar_todos_cnpj_dialog(items: list[dict]) -> None:
    total = len(items)
    resultado_key = "painel_consultar_todos_cnpj_resultado"

    def _mostrar_resultado(sucesso: int, erros: list[tuple[str, str]]) -> None:
        if sucesso:
            st.success(f"{sucesso} de {total} CNPJ(s) consultado(s) com sucesso.")
        for cnpj_label, motivo in erros:
            st.warning(f"{cnpj_label}: {motivo}")
        if st.button("Fechar", use_container_width=True, key="fechar_consultar_todos_cnpj"):
            st.session_state.pop(resultado_key, None)
            st.rerun()

    resultado = st.session_state.get(resultado_key)
    if resultado is not None:
        _mostrar_resultado(*resultado)
        return

    st.markdown(
        f"Isso vai consultar **{total} CNPJ(s)** no DJEN, até {DJE_BULK_CONSULTA_CONCORRENCIA} de cada "
        "vez. Pode levar alguns minutos, dependendo da resposta da API."
    )
    if st.button("Consultar todos", type="primary", use_container_width=True, key="confirmar_consultar_todos_cnpj"):
        progress = st.progress(0.0)
        status_placeholder = st.empty()
        erros: list[tuple[str, str]] = []
        sucesso = 0
        concluidos = 0
        # Só a busca (sem tocar em st.session_state) roda nas threads; a gravação do
        # resultado acontece aqui embaixo, sempre na thread principal.
        with ThreadPoolExecutor(max_workers=DJE_BULK_CONSULTA_CONCORRENCIA) as executor:
            futures = {executor.submit(_fetch_dje_cnpj_dados, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                dados = future.result()
                obteve_dados, mensagens_erro = _aplicar_dje_cnpj_dados(item["cnpj"], dados)
                if obteve_dados:
                    sucesso += 1
                if mensagens_erro:
                    erros.append((format_cnpj_br(item["cnpj"]), "; ".join(mensagens_erro)))
                concluidos += 1
                status_placeholder.caption(f"Consultando... {concluidos} de {total} concluído(s).")
                progress.progress(concluidos / total)
        status_placeholder.empty()
        st.session_state[resultado_key] = (sucesso, erros)
        _mostrar_resultado(sucesso, erros)


@st.dialog("Cadastrar processo TCU")
def show_add_tcu_process_dialog() -> None:
    with st.form("tcu_form", clear_on_submit=True):
        tcu_number = st.text_input("Número do processo (TC)", placeholder="Ex.: 012.345/2024-3", key="tcu_number")
        tcu_interessado = st.text_input("Interessado", placeholder="Ex.: Federação X", key="tcu_interessado")
        tcu_responsavel = st.text_input("Responsável", placeholder="Ex.: Advogado(a) responsável", key="tcu_responsavel")
        tcu_tipo = st.selectbox("Tipo", TCU_TIPOS, key="tcu_tipo")
        tcu_conecta_url_input = st.text_input(
            "Link do Conecta TCU (opcional, só se precisar sobrepor o link padrão)",
            placeholder="Ex.: https://conecta-tcu.apps.tcu.gov.br/tvp/12345678",
            help=(
                "Por padrão o botão \"Consultar\" já monta o link do Conecta TCU sozinho a partir do número do "
                "processo. Preencha aqui só se precisar apontar para uma URL diferente."
            ),
            key="tcu_conecta_url_field",
        )
        tcu_add = st.form_submit_button("Cadastrar processo", use_container_width=True)
    if tcu_add:
        try:
            numero_normalizado = normalizar_numero_tcu(tcu_number)
        except ValueError as exc:
            st.warning(str(exc))
        else:
            if any(p["number"] == numero_normalizado for p in st.session_state.tcu_processes):
                st.warning("Esse processo já está cadastrado.")
            else:
                st.session_state.tcu_processes.append({
                    "number": numero_normalizado,
                    "tipo": tcu_tipo,
                    "interessado": tcu_interessado.strip(),
                    "responsavel": tcu_responsavel.strip(),
                    "conecta_url": tcu_conecta_url_input.strip(),
                    "movements": [],
                    "movements_conecta": [],
                    "last_query": None,
                })
                st.success("Processo cadastrado.")
                st.rerun()


@st.dialog("Editar processo TCU")
def show_edit_tcu_process_dialog(index: int) -> None:
    item = st.session_state.tcu_processes[index]
    with st.form("tcu_edit_form"):
        edit_number = st.text_input("Número do processo (TC)", value=item["number"])
        edit_interessado = st.text_input("Interessado", value=item.get("interessado") or "")
        edit_responsavel = st.text_input("Responsável", value=item.get("responsavel") or "")
        edit_tipo = st.selectbox(
            "Tipo", TCU_TIPOS, index=TCU_TIPOS.index(item["tipo"]) if item.get("tipo") in TCU_TIPOS else 0
        )
        edit_conecta_url = st.text_input(
            "Link do Conecta TCU (opcional, só se precisar sobrepor o link padrão)",
            value=item.get("conecta_url") or "",
            placeholder="Ex.: https://conecta-tcu.apps.tcu.gov.br/tvp/12345678",
            help=(
                "Por padrão o botão \"Consultar\" já monta o link do Conecta TCU sozinho a partir do número do "
                "processo. Preencha aqui só se precisar apontar para uma URL diferente."
            ),
        )
        save_col, remove_col = st.columns(2)
        with save_col:
            save = st.form_submit_button("Salvar alterações", use_container_width=True)
        with remove_col:
            remove = st.form_submit_button("Remover processo", use_container_width=True)
    if save:
        try:
            numero_normalizado = normalizar_numero_tcu(edit_number)
        except ValueError as exc:
            st.warning(str(exc))
        else:
            if any(
                i != index and p["number"] == numero_normalizado for i, p in enumerate(st.session_state.tcu_processes)
            ):
                st.warning("Esse processo já está cadastrado.")
            else:
                st.session_state.tcu_processes[index] = {
                    **item,
                    "number": numero_normalizado,
                    "interessado": edit_interessado.strip(),
                    "responsavel": edit_responsavel.strip(),
                    "tipo": edit_tipo,
                    "conecta_url": edit_conecta_url.strip(),
                }
                st.success("Processo atualizado.")
                st.rerun()
    if remove:
        st.session_state.tcu_processes.pop(index)
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
        "Não exige credencial: a consulta usa a busca pública do TCU por número de processo. As movimentações "
        "são preenchidas automaticamente a partir dos e-mails do serviço \"Acompanhamento processual (Push)\" do "
        "próprio TCU, na conta Google conectada em Autenticações — o cadastro do processo no Push, porém, precisa "
        "ser feito uma vez pelo usuário no site do TCU, com login gov.br, apontando para esse mesmo e-mail."
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
        "usuario": "Sibylla Naoum",
        "nome": "Camargos Advogados",
        "cnpj": "12.345.678/0001-90",
        "endereco": "SHIS QI 5, Bloco A, Sala 302 · Lago Sul, Brasília/DF",
        "area_atuacao": "Direito Administrativo e Desportivo",
        "telefone": "(61) 99999-9999",
        "email": "camargosadvogados@gmail.com",
        "logo": load_logo_data_uri("cmsadvogados_logo.jpg"),
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
        ":material/mail: Links e E-mails",
        key="nav_links_button",
        type="primary" if _active_module == "Links e E-mails" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Links e E-mails"
        st.rerun()

    if st.button(
        ":material/key: Autenticações",
        key="nav_auth_button",
        type="primary" if _active_module == "Autenticações" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Autenticações"
        st.rerun()

    if st.button(
        ":material/menu_book: Tutorial",
        key="nav_tutorial_button",
        type="primary" if _active_module == "Tutorial" else "secondary",
        use_container_width=True,
    ):
        st.session_state.active_module = "Tutorial"
        st.rerun()

    if st.button(":material/settings: Configurações", key="nav_settings_button", use_container_width=True):
        show_settings_dialog()

    st.divider()
    st.caption("AMBIENTE PILOTO")
    st.caption("v0.1 · debug local")

if "process_number" not in st.session_state:
    st.session_state.process_number = st.session_state.processes[0]["number"] if st.session_state.processes else ""
process_number = st.session_state.process_number

render_alerts_panel()

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
                f'<div class="id-card-contact">{id_card_email}</div>'
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

    def _tcu_paste_import_widget(proc: dict) -> None:
        with st.expander(
            "Colar histórico do Conecta TCU",
            expanded=not proc.get("movements_conecta"),
        ):
            st.caption(
                "Na aba HISTÓRICO do Conecta TCU, selecione e copie as linhas do processo e cole abaixo. "
                "Formato esperado por linha: \"DD/MM/AAAA HH:MM:SS - descrição\"."
            )
            tcu_conecta_texto = st.text_area(
                "Colar histórico",
                height=150,
                key=f"painel_tcu_conecta_paste_{proc['number']}",
                label_visibility="collapsed",
            )
            if st.button("Importar", key=f"painel_tcu_conecta_import_{proc['number']}"):
                tcu_conecta_novos = importar_historico_conecta_tcu(proc, tcu_conecta_texto)
                if tcu_conecta_novos:
                    st.success(f"{tcu_conecta_novos} movimentação(ões) nova(s) importada(s).")
                else:
                    st.warning("Nenhuma movimentação nova reconhecida nesse texto.")

    def _abrir_dialog_painel_processo(kind: str, item: dict) -> None:
        if kind == "DJe":
            show_movimentacoes_dialog(
                f"{item['label']} · {item['number']}",
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
                notice=lambda numero=item["number"]: _render_dje_dialog_notices(numero),
            )
        elif kind == "TCU":
            _tcu_conectado_painel = google_account_connected()
            show_movimentacoes_dialog(
                f"TCU · {item['number']}",
                ultima_atualizacao=item.get("last_query"),
                consultar_link=item.get("conecta_url") or tcu_conecta_url(item["number"]),
                consultar_proc=item,
                refresh=lambda proc=item: {
                    "sources": {
                        "Push": movimentacoes_tcu_processo(proc),
                        "Conecta TCU": movimentacoes_tcu_conecta(proc),
                    },
                    "ultima_atualizacao": proc.get("last_query"),
                },
                sources={
                    "Push": movimentacoes_tcu_processo(item),
                    "Conecta TCU": movimentacoes_tcu_conecta(item),
                },
                default_source="Push",
                source_widgets={"Conecta TCU": lambda proc=item: _tcu_paste_import_widget(proc)},
                sincronizar_action=sincronizar_tcu_push,
                sincronizar_disabled=not _tcu_conectado_painel,
                sincronizar_help=(
                    "Lê a caixa do Gmail conectado em busca de e-mails de push do TCU."
                    if _tcu_conectado_painel else "Conecte sua conta Google em Autenticações primeiro."
                ),
                busca_publica_url=tcu_pesquisa_publica_url(item["number"]),
            )
        else:
            show_movimentacoes_dialog(
                f"{item['org']} · {item['number']}",
                movimentacoes_sei_processo(item),
                ultima_atualizacao=item.get("last_query"),
                consultar_link=sei_consultar_link(item),
                consultar_proc=item,
            )

    painel_tab_processos, painel_tab_cnpj = st.tabs(["Processos", "CNPJ"])

    with painel_tab_processos:
        st.session_state.setdefault("painel_proc_filters", {"sistemas": [], "responsaveis": []})
        if not st.session_state.processes and not st.session_state.sei_processes and not st.session_state.tcu_processes:
            status("Nenhum processo monitorado ainda. Cadastre um processo para começar.", "warn")
        else:
            painel_proc_refs = (
                [("DJe", item) for item in st.session_state.processes]
                + [("SEI", item) for item in st.session_state.sei_processes]
                + [("TCU", item) for item in st.session_state.tcu_processes]
            )

            painel_proc_search_col, painel_proc_hist_col = st.columns([3, 2])
            with painel_proc_search_col:
                st.markdown('<div class="eyebrow">Buscar processo:</div>', unsafe_allow_html=True)
                painel_proc_search = st.text_input(
                    "Buscar processo",
                    placeholder="Buscar por número, interessado, sistema ou órgão",
                    key="painel_proc_search",
                    label_visibility="collapsed",
                )

            painel_proc_toolbar = st.container(key="painel_proc_toolbar")

            painel_proc_filters = st.session_state["painel_proc_filters"]
            filtered_proc_refs = painel_proc_refs
            if painel_proc_filters["sistemas"]:
                filtered_proc_refs = [(k, item) for k, item in filtered_proc_refs if k in painel_proc_filters["sistemas"]]
            if painel_proc_filters["responsaveis"]:
                filtered_proc_refs = [
                    (k, item) for k, item in filtered_proc_refs
                    if (item.get("responsavel") or "não informado") in painel_proc_filters["responsaveis"]
                ]
            if painel_proc_search.strip():
                painel_proc_term = painel_proc_search.strip().lower()
                filtered_proc_refs = [
                    (k, item) for k, item in filtered_proc_refs
                    if painel_proc_term in item["number"].lower()
                    or painel_proc_term in (item["label"] if k == "DJe" else (item.get("interessado") or "")).lower()
                    or painel_proc_term in k.lower()
                    or painel_proc_term in (
                        resolve_orgao_label(item["number"]) if k == "DJe"
                        else "TCU" if k == "TCU"
                        else item["org"]
                    ).lower()
                ]

            painel_proc_dje_numeros = [item["number"] for k, item in filtered_proc_refs if k == "DJe"]

            with painel_proc_toolbar:
                if st.button(":material/filter_alt:", key="toolbar_filter_painel_proc", help="Filtrar"):
                    show_painel_proc_filter_dialog()
                if st.button(
                    ":material/sync:",
                    key="toolbar_consultar_todos_painel_proc",
                    help="Consultar todos os processos DJe filtrados no DataJud/DJEN",
                    disabled=not painel_proc_dje_numeros,
                ):
                    st.session_state.pop("painel_consultar_todos_proc_resultado", None)
                    show_painel_consultar_todos_proc_dialog(painel_proc_dje_numeros)

            selected_rows: list[int] = []
            if not filtered_proc_refs:
                status("Nenhum processo encontrado para os filtros selecionados.")
            else:
                painel_proc_rows = [
                    {
                        "Número do processo": item["number"],
                        "Interessado": item["label"] if kind == "DJe" else (item.get("interessado") or "não informado"),
                        "Sistema": kind,
                        "Órgão": (
                            resolve_orgao_label(item["number"]) if kind == "DJe"
                            else "TCU" if kind == "TCU"
                            else item["org"]
                        ),
                        "Responsável": item.get("responsavel") or "não informado",
                        "Última consulta": ultima_consulta_label(
                            st.session_state.query_timestamps.get(item["number"]) if kind == "DJe" else item.get("last_query")
                        ),
                    }
                    for kind, item in filtered_proc_refs
                ]
                painel_proc_styler = estilizar_responsavel(pd.DataFrame(painel_proc_rows)).apply(
                    _ultima_consulta_row_style, axis=1
                )
                selection = st.dataframe(
                    painel_proc_styler,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="painel_proc_table",
                )
                selected_rows = selection.get("selection", {}).get("rows", []) if selection else []

            with painel_proc_hist_col:
                st.markdown('<div class="eyebrow">Ver histórico do processo:</div>', unsafe_allow_html=True)
                if st.button(
                    "Consultar",
                    key="painel_proc_ver_historico",
                    type="primary",
                    disabled=not selected_rows,
                    use_container_width=True,
                ):
                    kind, item = filtered_proc_refs[selected_rows[0]]
                    _abrir_dialog_painel_processo(kind, item)

    with painel_tab_cnpj:
        st.session_state.setdefault("painel_cnpj_filters", {"responsaveis": []})
        if not st.session_state.monitored_cnpjs:
            status("Nenhum CNPJ monitorado ainda. Cadastre um CNPJ para começar.", "warn")
        else:
            painel_cnpj_search_col, painel_cnpj_hist_col = st.columns([3, 2])
            with painel_cnpj_search_col:
                st.markdown('<div class="eyebrow">Buscar CNPJ:</div>', unsafe_allow_html=True)
                painel_cnpj_search = st.text_input(
                    "Buscar CNPJ",
                    placeholder="Buscar por CNPJ, razão social ou interessado",
                    key="painel_cnpj_search",
                    label_visibility="collapsed",
                )

            painel_cnpj_toolbar = st.container(key="painel_cnpj_toolbar")

            painel_cnpj_filters = st.session_state["painel_cnpj_filters"]
            filtered_cnpj_items = st.session_state.monitored_cnpjs
            if painel_cnpj_filters["responsaveis"]:
                filtered_cnpj_items = [
                    item for item in filtered_cnpj_items
                    if (item.get("responsavel") or "não informado") in painel_cnpj_filters["responsaveis"]
                ]
            if painel_cnpj_search.strip():
                painel_cnpj_term = painel_cnpj_search.strip().lower()
                filtered_cnpj_items = [
                    item for item in filtered_cnpj_items
                    if painel_cnpj_term in format_cnpj_br(item["cnpj"]).lower()
                    or painel_cnpj_term in item["cnpj"].lower()
                    or painel_cnpj_term in item["label"].lower()
                    or painel_cnpj_term in (item.get("interessado") or "").lower()
                ]

            with painel_cnpj_toolbar:
                if st.button(":material/filter_alt:", key="toolbar_filter_painel_cnpj", help="Filtrar"):
                    show_painel_cnpj_filter_dialog()
                if st.button(
                    ":material/sync:",
                    key="toolbar_consultar_todos_painel_cnpj",
                    help="Consultar todos os CNPJs filtrados no DJEN",
                    disabled=not filtered_cnpj_items,
                ):
                    st.session_state.pop("painel_consultar_todos_cnpj_resultado", None)
                    show_painel_consultar_todos_cnpj_dialog(filtered_cnpj_items)

            cnpj_selected_rows: list[int] = []
            if not filtered_cnpj_items:
                status("Nenhum CNPJ encontrado para os filtros selecionados.")
            else:
                painel_cnpj_rows = [
                    {
                        "CNPJ": format_cnpj_br(item["cnpj"]),
                        "Interessado": item.get("interessado") or "não informado",
                        "Sistema": "DJe",
                        "Responsável": item.get("responsavel") or "não informado",
                        "Razão Social": item["label"],
                        "Última consulta": ultima_consulta_label(st.session_state.cnpj_query_timestamps.get(item["cnpj"])),
                    }
                    for item in filtered_cnpj_items
                ]
                painel_cnpj_styler = estilizar_responsavel(pd.DataFrame(painel_cnpj_rows)).apply(
                    _ultima_consulta_row_style, axis=1
                )
                cnpj_selection = st.dataframe(
                    painel_cnpj_styler,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="painel_cnpj_table",
                )
                cnpj_selected_rows = cnpj_selection.get("selection", {}).get("rows", []) if cnpj_selection else []

            with painel_cnpj_hist_col:
                st.markdown('<div class="eyebrow">Ver histórico do CNPJ:</div>', unsafe_allow_html=True)
                if st.button(
                    "Consultar",
                    key="painel_cnpj_ver_historico",
                    type="primary",
                    disabled=not cnpj_selected_rows,
                    use_container_width=True,
                ):
                    item = filtered_cnpj_items[cnpj_selected_rows[0]]
                    show_movimentacoes_dialog(
                        item["label"],
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
                        notice=render_djen_indisponivel_notice
                        if (st.session_state.djen_cnpj_results.get(item["cnpj"]) or {}).get("_mock")
                        else None,
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

    mon_tab_dje, mon_tab_det, mon_tab_sei, mon_tab_tcu = st.tabs(PLATAFORMAS)

    with mon_tab_dje:
        mon_cons_tab_cnpj, mon_cons_tab_cnj = st.tabs(["CNPJ", "Processos"])

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

                if djen_response and djen_response.get("_mock"):
                    render_djen_indisponivel_notice()
                if datajud_result and datajud_result.get("_mock"):
                    render_datajud_indisponivel_notice()

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

                if djen_cnpj_response and djen_cnpj_response.get("_mock"):
                    render_djen_indisponivel_notice()

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
        sei_cons_tab_labels = [SEI_TODOS_ORGAOS] + st.session_state.sei_orgaos
        sei_cons_tabs = st.tabs(sei_cons_tab_labels)

        with sei_cons_tabs[0]:
            st.session_state.setdefault("sei_todos_filters", {"orgaos": [], "status": []})

            search_col, ver_historico_col = st.columns([3, 2])
            with search_col:
                st.markdown('<div class="eyebrow">Buscar processo:</div>', unsafe_allow_html=True)
                sei_search_all = st.text_input(
                    "Buscar processo",
                    placeholder="Buscar por número, interessado ou órgão",
                    key="sei_search_todos",
                    label_visibility="collapsed",
                )

            filter_row = st.container(key="sei_todos_toolbar")

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

            selected_rows: list[int] = []

            with filter_row:
                if st.button(":material/filter_alt:", key="toolbar_filter_sei_todos", help="Filtrar"):
                    show_sei_todos_filter_dialog()

            if not filtered_all:
                status("Nenhum processo encontrado para os filtros selecionados.")
            else:
                table_rows = [
                    {
                        "Número": proc["number"],
                        "Órgão": proc["org"],
                        "Interessado": proc.get("interessado") or "não informado",
                        "Responsável": proc.get("responsavel") or "não informado",
                        "Link de acesso": sei_consultar_link(proc),
                        "Status do link": sei_link_status(proc)[0],
                    }
                    for proc in filtered_all
                ]
                selection = st.dataframe(
                    estilizar_responsavel(pd.DataFrame(table_rows)),
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="sei_todos_table",
                    column_config={
                        "Número": st.column_config.TextColumn("Número", width="small"),
                        "Órgão": st.column_config.TextColumn("Órgão", width="medium"),
                        "Interessado": st.column_config.TextColumn("Interessado", width="medium"),
                        "Responsável": st.column_config.TextColumn("Responsável", width="medium"),
                        "Link de acesso": st.column_config.LinkColumn(
                            "Link de acesso", display_text="Abrir ↗", width="small"
                        ),
                        "Status do link": st.column_config.TextColumn("Status do link", width="medium"),
                    },
                )
                selected_rows = selection.get("selection", {}).get("rows", []) if selection else []

            with ver_historico_col:
                st.markdown(
                    '<div class="eyebrow">Selecione um processo para consultar.</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Consultar movimentações",
                    key="sei_todos_ver_historico",
                    type="primary",
                    disabled=not selected_rows,
                    use_container_width=True,
                ):
                    selected_proc = filtered_all[selected_rows[0]]
                    show_movimentacoes_dialog(
                        f"{selected_proc['org']} · {selected_proc['number']}",
                        movimentacoes_sei_processo(selected_proc),
                        ultima_atualizacao=selected_proc.get("last_query"),
                        consultar_link=sei_consultar_link(selected_proc),
                        consultar_proc=selected_proc,
                    )

        for sei_org_tab, sei_org_name in zip(sei_cons_tabs[1:], st.session_state.sei_orgaos):
            with sei_org_tab:
                org_processes = [p for p in st.session_state.sei_processes if p["org"] == sei_org_name]

                if not org_processes:
                    status(f"Nenhum processo cadastrado para {sei_org_name}. Cadastre um processo para consultar.", "warn")
                else:
                    process_options = [
                        f"{p['number']} · {p.get('interessado') or 'sem interessado'}" for p in org_processes
                    ]
                    select_process_col, _spacer_col = st.columns([2, 3])
                    with select_process_col:
                        st.markdown('<div class="eyebrow">Selecionar processo:</div>', unsafe_allow_html=True)
                        selected_process = st.selectbox(
                            "Selecionar processo para consulta",
                            process_options,
                            key=f"sei_select_process_{sei_org_name}",
                            label_visibility="collapsed",
                        )
                    selected_index = process_options.index(selected_process)
                    proc = org_processes[selected_index]

                    link = sei_consultar_link(proc)

                    consultar_col, info_col = st.columns([4, 1])
                    with consultar_col:
                        st.link_button(
                            "Consultar movimentações",
                            link or "#",
                            type="primary",
                            use_container_width=True,
                            disabled=not link,
                            key=f"consultar_sei_{sei_org_name}",
                        )
                    with info_col:
                        if st.button("Informações", key=f"info_sei_{sei_org_name}", use_container_width=True):
                            show_monitoramento_info_dialog("SEI")

                    if not link:
                        if proc.get("forma_acesso") == "Consulta pública":
                            status(
                                f"Link do portal de consulta pública não cadastrado para {sei_org_name}.", "warn"
                            )
                        else:
                            status("Link de acesso não cadastrado para este processo. Cadastre em Links e E-mails.", "warn")

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
        _tcu_conectado = google_account_connected()

        if not st.session_state.tcu_processes:
            status("Nenhum processo TCU cadastrado ainda. Cadastre um processo para consultar.", "warn")
        else:
            tcu_process_options = [
                f"{p['number']} · {p.get('interessado') or 'sem interessado'}" for p in st.session_state.tcu_processes
            ]
            select_tcu_col, sync_tcu_col = st.columns([2, 3])
            with select_tcu_col:
                st.markdown('<div class="eyebrow">Selecionar processo:</div>', unsafe_allow_html=True)
                selected_tcu_process = st.selectbox(
                    "Selecionar processo TCU",
                    tcu_process_options,
                    key="tcu_select_process",
                    label_visibility="collapsed",
                )
            with sync_tcu_col:
                st.markdown('<div class="eyebrow">Sincronizar com Push:</div>', unsafe_allow_html=True)
                if st.button(
                    "Sincronizar",
                    use_container_width=True,
                    key="sincronizar_tcu",
                    disabled=not _tcu_conectado,
                    help="Lê a caixa do Gmail conectado em busca de e-mails de push do TCU."
                    if _tcu_conectado else "Conecte sua conta Google em Autenticações primeiro.",
                ):
                    with st.spinner("Sincronizando..."):
                        tcu_novos, tcu_avisos = sincronizar_tcu_push()
                    if tcu_novos:
                        st.success(f"{tcu_novos} nova(s) movimentação(ões) importada(s).")
                    elif not tcu_avisos:
                        st.info("Nenhuma movimentação nova encontrada.")
                    for tcu_aviso in tcu_avisos:
                        st.warning(tcu_aviso)

            selected_tcu_index = tcu_process_options.index(selected_tcu_process)
            tcu_proc = st.session_state.tcu_processes[selected_tcu_index]

            tcu_consultar_url = tcu_proc.get("conecta_url") or tcu_conecta_url(tcu_proc["number"])

            consultar_tcu_col, info_tcu_col = st.columns([4, 1])
            with consultar_tcu_col:
                st.link_button(
                    "Consultar no Conecta TCU",
                    tcu_consultar_url,
                    type="primary",
                    use_container_width=True,
                    key="consultar_tcu_processo",
                )
            st.caption(
                "Exige login no Conecta TCU (histórico completo). Sem login? "
                f"[Busca pública, sem login ↗]({tcu_pesquisa_publica_url(tcu_proc['number'])})"
            )
            with info_tcu_col:
                if st.button("Informações", key="info_tcu", use_container_width=True):
                    show_monitoramento_info_dialog("TCU")

            tcu_ultima_data, tcu_ultima_descricao = ultima_movimentacao_tcu(tcu_proc)
            tcu_last_query = tcu_proc.get("last_query")

            tcu_summary_a, tcu_summary_b, tcu_summary_c = st.columns(3)
            with tcu_summary_a:
                card(
                    "INTERESSADO",
                    tcu_proc.get("interessado") or "não informado",
                    tcu_proc.get("responsavel") or "sem responsável",
                )
            with tcu_summary_b:
                card(
                    "ÚLTIMA MOVIMENTAÇÃO",
                    tcu_ultima_data.strftime("%d/%m/%Y") if tcu_ultima_data else "—",
                    tcu_ultima_descricao or "sem registro",
                )
            with tcu_summary_c:
                tcu_last_query_label = tcu_last_query.strftime("%d/%m/%Y %H:%M") if tcu_last_query else "—"
                card("ÚLTIMA CONSULTA", tcu_last_query_label, "data e hora")

            st.markdown(
                '<div class="eyebrow" style="margin-top:1.2rem;">Movimentações registradas:</div>',
                unsafe_allow_html=True,
            )
            tcu_fonte = st.segmented_control(
                "Fonte",
                ["Push", "Conecta TCU"],
                default="Push",
                key=f"tcu_fonte_{tcu_proc['number']}",
                label_visibility="collapsed",
            ) or "Push"

            if tcu_fonte == "Push":
                tcu_mov_rows = movimentacoes_tcu_processo(tcu_proc)
                if tcu_mov_rows:
                    tcu_mov_rows_sorted = sorted(tcu_mov_rows, key=lambda r: r.get("Data") or date.min, reverse=True)
                    st.dataframe(
                        tcu_mov_rows_sorted,
                        use_container_width=True,
                        hide_index=True,
                        column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
                    )
                else:
                    status(
                        "Nenhuma movimentação via Push ainda. Sincronize ou aguarde a próxima movimentação.", "warn"
                    )
            else:
                with st.expander(
                    "Colar histórico do Conecta TCU",
                    expanded=not tcu_proc.get("movements_conecta"),
                ):
                    st.caption(
                        "Na aba HISTÓRICO do Conecta TCU, selecione e copie as linhas do processo e cole abaixo. "
                        "Formato esperado por linha: \"DD/MM/AAAA HH:MM:SS - descrição\"."
                    )
                    tcu_conecta_texto = st.text_area(
                        "Colar histórico",
                        height=150,
                        key=f"tcu_conecta_paste_{tcu_proc['number']}",
                        label_visibility="collapsed",
                    )
                    if st.button("Importar", key=f"tcu_conecta_import_{tcu_proc['number']}"):
                        tcu_conecta_novos = importar_historico_conecta_tcu(tcu_proc, tcu_conecta_texto)
                        if tcu_conecta_novos:
                            st.success(f"{tcu_conecta_novos} movimentação(ões) nova(s) importada(s).")
                        else:
                            st.warning("Nenhuma movimentação nova reconhecida nesse texto.")
                        st.rerun()

                tcu_mov_rows_conecta = movimentacoes_tcu_conecta(tcu_proc)
                if tcu_mov_rows_conecta:
                    tcu_mov_rows_conecta_sorted = sorted(
                        tcu_mov_rows_conecta, key=lambda r: r.get("Data") or date.min, reverse=True
                    )
                    st.dataframe(
                        tcu_mov_rows_conecta_sorted,
                        use_container_width=True,
                        hide_index=True,
                        column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
                    )
                else:
                    status("Nenhuma movimentação do Conecta TCU importada ainda.", "warn")

elif module == "Cadastro":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Cadastro.</h1>'
        '<div class="lede">Cadastre processos e CNPJs monitorados de qualquer sistema, tudo em um único lugar.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    CADASTRO_SISTEMAS = ["DJe", "SEI", "TCU"]

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

            processo_toolbar = st.container(key="processo_toolbar")
            processo_selected_rows: list[int] = []
            filtered_processes: list[dict] = []

            processo_filters = st.session_state.processo_filters
            filtered_processes = st.session_state.processes
            if processo_filters["orgaos"]:
                filtered_processes = [
                    p for p in filtered_processes if resolve_orgao_label(p["number"]) in processo_filters["orgaos"]
                ]

            if not filtered_processes:
                status("Nenhum processo cadastrado ainda.")
            else:
                processo_table_rows = [
                    {
                        "Número do processo": p["number"],
                        "Interessado": p["label"],
                        "Órgão": resolve_orgao_label(p["number"]),
                        "Responsável": p.get("responsavel") or "não informado",
                    }
                    for p in filtered_processes
                ]
                processo_selection = st.dataframe(
                    estilizar_responsavel(pd.DataFrame(processo_table_rows)),
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="processo_table",
                )
                st.caption("Clique em uma linha para selecioná-la e habilitar o ícone de edição acima.")
                processo_selected_rows = (
                    processo_selection.get("selection", {}).get("rows", []) if processo_selection else []
                )

            with processo_toolbar:
                if st.button(":material/filter_alt:", key="toolbar_filter_processo", help="Filtrar"):
                    show_process_filter_dialog()
                if st.button(":material/add:", key="toolbar_add_processo", help="Cadastrar processo"):
                    show_add_process_dialog()
                if st.button(
                    ":material/edit:", key="toolbar_edit_processo", help="Editar processo",
                    disabled=not processo_selected_rows,
                ):
                    p = filtered_processes[processo_selected_rows[0]]
                    orig_index_by_number = {item["number"]: i for i, item in enumerate(st.session_state.processes)}
                    show_edit_process_dialog(orig_index_by_number[p["number"]])
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

        with cad_tab_cnpj:
            st.session_state.setdefault("cnpj_delete_open", False)

            cnpj_toolbar = st.container(key="cnpj_toolbar")
            cnpj_selected_rows: list[int] = []
            filtered_cnpjs = st.session_state.monitored_cnpjs

            if not filtered_cnpjs:
                status("Nenhum CNPJ cadastrado.", "warn")
            else:
                cnpj_table_rows = [
                    {
                        "CNPJ": format_cnpj_br(item["cnpj"]),
                        "Interessado": item.get("interessado") or "não informado",
                        "Responsável": item.get("responsavel") or "não informado",
                        "Razão Social": item["label"],
                    }
                    for item in filtered_cnpjs
                ]
                cnpj_selection = st.dataframe(
                    estilizar_responsavel(pd.DataFrame(cnpj_table_rows)),
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="cnpj_table",
                )
                st.caption("Clique em uma linha para selecioná-la e habilitar o ícone de edição acima.")
                cnpj_selected_rows = cnpj_selection.get("selection", {}).get("rows", []) if cnpj_selection else []

            with cnpj_toolbar:
                if st.button(":material/add:", key="toolbar_add_cnpj", help="Cadastrar CNPJ"):
                    show_add_cnpj_dialog()
                if st.button(
                    ":material/edit:", key="toolbar_edit_cnpj", help="Editar CNPJ", disabled=not cnpj_selected_rows,
                ):
                    item = filtered_cnpjs[cnpj_selected_rows[0]]
                    orig_index_by_cnpj = {c["cnpj"]: i for i, c in enumerate(st.session_state.monitored_cnpjs)}
                    show_edit_cnpj_dialog(orig_index_by_cnpj[item["cnpj"]])
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

    elif cadastro_sistema == "SEI":
        SEI_CAD_TODOS = "Todos os processos"
        sei_cad_tab_labels = [SEI_CAD_TODOS] + st.session_state.sei_orgaos + ["+"]
        sei_cad_org_tabs = st.tabs(sei_cad_tab_labels)

        with sei_cad_org_tabs[0]:
            st.session_state.setdefault("sei_delete_open_todos", False)
            st.session_state.setdefault("sei_filters_todos", {"formas_acesso": [], "orgaos": []})

            sei_toolbar_todos = st.container(key="sei_toolbar_todos")
            sei_selected_rows_todos: list[int] = []
            filtered_processes_todos: list[dict] = []

            sei_filters_todos = st.session_state["sei_filters_todos"]
            filtered_processes_todos = st.session_state.sei_processes
            if sei_filters_todos["orgaos"]:
                filtered_processes_todos = [p for p in filtered_processes_todos if p["org"] in sei_filters_todos["orgaos"]]
            if sei_filters_todos["formas_acesso"]:
                filtered_processes_todos = [
                    p for p in filtered_processes_todos if p.get("forma_acesso") in sei_filters_todos["formas_acesso"]
                ]

            if not filtered_processes_todos:
                status("Nenhum processo encontrado.")
            else:
                sei_table_rows_todos = [
                    {
                        "Número": proc["number"],
                        "Interessado": proc.get("interessado") or "não informado",
                        "Órgão": proc["org"],
                        "Responsável": proc.get("responsavel") or "não informado",
                        "Abrir": sei_consultar_link(proc),
                        "Forma de acesso": proc.get("forma_acesso") or "—",
                        "Status do link": sei_link_status(proc)[0],
                    }
                    for proc in filtered_processes_todos
                ]
                sei_selection_todos = st.dataframe(
                    estilizar_responsavel(pd.DataFrame(sei_table_rows_todos)),
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="sei_table_todos",
                    column_config={
                        "Abrir": st.column_config.LinkColumn("Abrir", display_text="Abrir ↗", width="small"),
                    },
                )
                st.caption("Clique em uma linha para selecioná-la e habilitar o ícone de edição acima.")
                sei_selected_rows_todos = sei_selection_todos.get("selection", {}).get("rows", []) if sei_selection_todos else []

            with sei_toolbar_todos:
                if st.button(":material/filter_alt:", key="toolbar_filter_sei_todos_cad", help="Filtrar"):
                    show_sei_cadastro_todos_filter_dialog()
                if st.button(":material/add:", key="toolbar_add_sei_todos_cad", help="Cadastrar processo administrativo"):
                    show_add_sei_process_dialog()
                if st.button(
                    ":material/edit:", key="toolbar_edit_sei_todos_cad", help="Editar processo",
                    disabled=not sei_selected_rows_todos,
                ):
                    proc = filtered_processes_todos[sei_selected_rows_todos[0]]
                    orig_index_by_id = {id(p): i for i, p in enumerate(st.session_state.sei_processes)}
                    show_edit_sei_process_dialog(orig_index_by_id[id(proc)])
                if st.button(":material/delete:", key="toolbar_delete_sei_todos_cad", help="Excluir"):
                    st.session_state["sei_delete_open_todos"] = not st.session_state["sei_delete_open_todos"]

            if st.session_state["sei_delete_open_todos"] and st.session_state.sei_processes:
                sei_delete_options_todos = [
                    f"{p['org']} · {p['number']} · {p.get('interessado') or 'sem interessado'}"
                    for p in st.session_state.sei_processes
                ]
                sei_del_col_todos, sei_confirm_col_todos = st.columns([3, 1])
                with sei_del_col_todos:
                    sei_delete_choice_todos = st.selectbox(
                        "Selecionar processo para excluir",
                        sei_delete_options_todos,
                        label_visibility="collapsed",
                        key="sei_delete_select_todos",
                    )
                with sei_confirm_col_todos:
                    if st.button("Excluir", key="sei_delete_confirm_todos", use_container_width=True):
                        proc_to_remove = st.session_state.sei_processes[sei_delete_options_todos.index(sei_delete_choice_todos)]
                        st.session_state.sei_processes.remove(proc_to_remove)
                        st.session_state["sei_delete_open_todos"] = False
                        st.success("Processo removido.")
                        st.rerun()

        for sei_org_tab, sei_org_name in zip(sei_cad_org_tabs[1:-1], st.session_state.sei_orgaos):
            with sei_org_tab:
                org_processes = [p for p in st.session_state.sei_processes if p["org"] == sei_org_name]
                st.session_state.setdefault(f"sei_delete_open_{sei_org_name}", False)
                st.session_state.setdefault(f"sei_filters_{sei_org_name}", {"formas_acesso": []})

                sei_toolbar = st.container(key=f"sei_toolbar_{sei_org_name}")
                sei_selected_rows: list[int] = []
                filtered_processes: list[dict] = []

                sei_filters = st.session_state[f"sei_filters_{sei_org_name}"]
                filtered_processes = org_processes
                if sei_filters["formas_acesso"]:
                    filtered_processes = [p for p in filtered_processes if p.get("forma_acesso") in sei_filters["formas_acesso"]]

                if not filtered_processes:
                    status(f"Nenhum processo encontrado para {sei_org_name}.")
                else:
                    sei_table_rows = [
                        {
                            "Número": proc["number"],
                            "Interessado": proc.get("interessado") or "não informado",
                            "Responsável": proc.get("responsavel") or "não informado",
                            "Abrir": sei_consultar_link(proc),
                            "Forma de acesso": proc.get("forma_acesso") or "—",
                            "Status do link": sei_link_status(proc)[0],
                        }
                        for proc in filtered_processes
                    ]
                    sei_selection = st.dataframe(
                        estilizar_responsavel(pd.DataFrame(sei_table_rows)),
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"sei_table_{sei_org_name}",
                        column_config={
                            "Abrir": st.column_config.LinkColumn("Abrir", display_text="Abrir ↗", width="small"),
                        },
                    )
                    st.caption("Clique em uma linha para selecioná-la e habilitar o ícone de edição acima.")
                    sei_selected_rows = sei_selection.get("selection", {}).get("rows", []) if sei_selection else []

                with sei_toolbar:
                    if st.button(":material/filter_alt:", key=f"toolbar_filter_sei_{sei_org_name}", help="Filtrar"):
                        show_sei_filter_dialog(sei_org_name)
                    if st.button(":material/add:", key=f"toolbar_add_sei_{sei_org_name}", help="Cadastrar processo administrativo"):
                        show_add_sei_process_dialog(sei_org_name)
                    if st.button(
                        ":material/edit:", key=f"toolbar_edit_sei_{sei_org_name}", help="Editar processo",
                        disabled=not sei_selected_rows,
                    ):
                        proc = filtered_processes[sei_selected_rows[0]]
                        orig_index_by_id = {id(p): i for i, p in enumerate(st.session_state.sei_processes)}
                        show_edit_sei_process_dialog(orig_index_by_id[id(proc)])
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

        with sei_cad_org_tabs[-1]:
            st.markdown('<div class="eyebrow">Adicionar novo órgão</div>', unsafe_allow_html=True)
            if st.button("Adicionar órgão", key="open_add_sei_orgao_dialog"):
                show_add_sei_orgao_dialog()

    elif cadastro_sistema == "TCU":
        st.session_state.setdefault("tcu_delete_open", False)
        st.session_state.setdefault("tcu_filters", {"tipos": []})

        tcu_toolbar = st.container(key="tcu_toolbar")
        tcu_selected_rows: list[int] = []
        filtered_tcu_processes: list[dict] = []

        st.link_button(
            "Acessar Push do TCU ↗",
            TCU_PUSH_CADASTRO_URL,
            help=(
                "Abre o site do TCU para cadastrar o acompanhamento processual (Push) — feito uma vez por "
                "processo, com login gov.br, apontando para o e-mail conectado em Autenticações."
            ),
        )

        tcu_filters = st.session_state.tcu_filters
        filtered_tcu_processes = st.session_state.tcu_processes
        if tcu_filters["tipos"]:
            filtered_tcu_processes = [p for p in filtered_tcu_processes if p.get("tipo") in tcu_filters["tipos"]]

        if not filtered_tcu_processes:
            status("Nenhum processo TCU cadastrado ainda.")
        else:
            tcu_table_rows = [
                {
                    "Número (TC)": p["number"],
                    "Interessado": p.get("interessado") or "não informado",
                    "Responsável": p.get("responsavel") or "não informado",
                    "Tipo": p.get("tipo") or "—",
                }
                for p in filtered_tcu_processes
            ]
            tcu_selection = st.dataframe(
                estilizar_responsavel(pd.DataFrame(tcu_table_rows)),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="tcu_table",
            )
            st.caption("Clique em uma linha para selecioná-la e habilitar o ícone de edição acima.")
            tcu_selected_rows = tcu_selection.get("selection", {}).get("rows", []) if tcu_selection else []

        with tcu_toolbar:
            if st.button(":material/filter_alt:", key="toolbar_filter_tcu", help="Filtrar"):
                show_tcu_filter_dialog()
            if st.button(":material/add:", key="toolbar_add_tcu", help="Cadastrar processo TCU"):
                show_add_tcu_process_dialog()
            if st.button(
                ":material/edit:", key="toolbar_edit_tcu", help="Editar processo", disabled=not tcu_selected_rows,
            ):
                proc = filtered_tcu_processes[tcu_selected_rows[0]]
                orig_index_by_id = {id(p): i for i, p in enumerate(st.session_state.tcu_processes)}
                show_edit_tcu_process_dialog(orig_index_by_id[id(proc)])
            if st.button(":material/delete:", key="toolbar_delete_tcu", help="Excluir"):
                st.session_state.tcu_delete_open = not st.session_state.tcu_delete_open

        if st.session_state.tcu_delete_open and st.session_state.tcu_processes:
            tcu_delete_options = [
                f"{p['number']} · {p.get('interessado') or 'sem interessado'}" for p in st.session_state.tcu_processes
            ]
            tcu_del_col, tcu_confirm_col = st.columns([3, 1])
            with tcu_del_col:
                tcu_delete_choice = st.selectbox(
                    "Selecionar processo para excluir",
                    tcu_delete_options,
                    label_visibility="collapsed",
                    key="tcu_delete_select",
                )
            with tcu_confirm_col:
                if st.button("Excluir", key="tcu_delete_confirm", use_container_width=True):
                    idx = tcu_delete_options.index(tcu_delete_choice)
                    st.session_state.tcu_processes.pop(idx)
                    st.session_state.tcu_delete_open = False
                    st.success("Processo removido.")
                    st.rerun()

elif module == "Links e E-mails":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Links e E-mails.</h1>'
        '<div class="lede">Controle central dos links de acesso, do prazo de validade de cada credencial usada '
        'pelos conectores (SEI, DET e demais órgãos) e do e-mail remetente das solicitações de renovação.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.session_state.setdefault("cred_filters", {"orgaos": []})

    st.markdown('<div class="eyebrow">LINKS CADASTRADOS</div>', unsafe_allow_html=True)
    st.caption("Cadastre, edite e monitore Links de acesso a processos restritos pela tabela abaixo.")

    # Container declarado aqui, mas preenchido só depois da tabela (abaixo), para o lápis
    # de editar já nascer sabendo qual linha está selecionada.
    cred_toolbar = st.container(key="cred_toolbar")
    cred_selected_rows: list[int] = []
    filtered_creds: list[tuple[int, dict]] = []

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
                    "Identificador": item.get("nome") or "—",
                    "Órgão": item["org"],
                    "Processo vinculado": item.get("processo") or "Geral",
                    "Link": item.get("link") or None,
                    "Validade": item["validade"].strftime("%d/%m/%Y") if item.get("validade") else "—",
                    "Status": credencial_status(item.get("validade"))[0],
                    "E-mail remetente": ", ".join(item.get("emails") or []) or "—",
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
            cred_selected_rows = cred_selection.get("selection", {}).get("rows", []) if cred_selection else []

    with cred_toolbar:
        if st.button(":material/filter_alt:", key="toolbar_filter_cred", help="Filtrar"):
            show_cred_filter_dialog()
        if st.button(":material/add:", key="toolbar_add_cred", help="Cadastrar link de acesso"):
            show_add_credencial_dialog()
        if st.button(
            ":material/edit:", key="toolbar_edit_cred", help="Editar credencial e e-mail remetente",
            disabled=not cred_selected_rows,
        ):
            show_edit_credencial_dialog(filtered_creds[cred_selected_rows[0]][0])

    st.markdown('<div class="eyebrow">E-MAIL PADRÃO DE SOLICITAÇÃO DE RENOVAÇÃO</div>', unsafe_allow_html=True)
    st.caption(
        "Este é o e-mail usado quando você clica em \"Solicitar novo link\" no Painel Geral — um e-mail é gerado "
        "separadamente para cada processo. O envio é semiautomático: você revisa o texto e os destinatários antes "
        "de confirmar o envio. Placeholders disponíveis: {processo}, {orgao}, {link}, {validade}, {status} (ex.: "
        "\"vencido há 8 dia(s)\"), {usuario}, {escritorio}."
    )
    with st.form("email_template_form"):
        template_assunto = st.text_input(
            "Assunto", value=st.session_state.email_template["assunto"], key="email_template_assunto_input"
        )
        template_corpo = st.text_area(
            "Corpo", value=st.session_state.email_template["corpo"], height=220, key="email_template_corpo_input"
        )
        save_template = st.form_submit_button("Salvar e-mail padrão", use_container_width=True)
    if save_template:
        if not template_assunto.strip() or not template_corpo.strip():
            st.warning("Informe o assunto e o corpo do e-mail.")
        else:
            st.session_state.email_template = {"assunto": template_assunto.strip(), "corpo": template_corpo}
            st.success("E-mail padrão atualizado.")
            st.rerun()

elif module == "Autenticações":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Autenticações.</h1>'
        '<div class="lede">Contas e credenciais que você cadastra e mantém para acessar os sistemas externos.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="eyebrow">CONTA GOOGLE (LOGIN)</div>', unsafe_allow_html=True)
    _remetente = st.session_state.firm_profile.get("email") or ""
    if _remetente:
        status(f"E-mail do escritório (cadastrado no Perfil): {html.escape(_remetente)}", "ok")
    else:
        status("Nenhum e-mail cadastrado no Perfil do escritório ainda. Cadastre em Perfil do escritório, na tela inicial.", "warn")

    if not is_gmail_address(_remetente):
        status(
            "O e-mail acima não é do Gmail, então o login com Google não se aplica — não é possível conectar uma "
            "conta que não seja @gmail.com. Ao clicar em \"Solicitar novo link\", a solicitação de cada processo "
            "abre pronta no Gmail, Outlook ou no seu app de e-mail padrão para você enviar manualmente.",
            "neutral",
        )
    else:
        _oauth_connected = bool(st.session_state.email_sender_config.get("oauth_account"))
        if _oauth_connected:
            status("Conta Google conectada. O envio de \"Solicitar novo link\" acontece automaticamente.", "ok")
            if st.button("Desconectar conta Google", key="oauth_google_disconnect_button"):
                desconectar_conta_google()
                st.rerun()
        else:
            status("Conecte sua conta Google para permitir o envio automático via Gmail.", "warn")
            _client_ready = _google_oauth_client_config() is not None
            if not _client_ready:
                status(
                    "Credenciais do app Google ainda não configuradas pelo administrador do sistema.",
                    "neutral",
                )
            if st.button(
                ":material/login: Conectar com Google",
                key="oauth_google_connect_button",
                disabled=not _client_ready,
                help="Abre o navegador para você fazer login e autorizar o envio." if _client_ready
                else "Credenciais do app Google não configuradas.",
                use_container_width=True,
            ):
                with st.spinner("Aguardando login no navegador..."):
                    ok, msg = conectar_conta_google()
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown('<div class="eyebrow">CREDENCIAIS</div>', unsafe_allow_html=True)
    st.caption(
        "Cadastre aqui as demais autenticações que você usa no dia a dia: e-mail, SEI, GOV.br, chaves de API "
        "(DataJud, DJEN, DJe, TCU) e qualquer outro órgão que vier a ser integrado. No campo \"Chave\", use apenas "
        "um identificador — não é preciso saber o nome técnico usado no sistema."
    )

    auth_toolbar = st.container(key="auth_toolbar")
    auth_selected_rows: list[int] = []

    if not st.session_state.auth_credenciais:
        status("Nenhuma autenticação cadastrada ainda.", "warn")
    else:
        auth_table_rows = [
            {
                "Chave": item.get("chave") or "—",
                "Sistema/Órgão": item.get("sistema") or "—",
                "Usuário/Login": item.get("usuario") or "—",
                "Senha/Chave": mask_secret(item.get("valor")),
                "Observação": item.get("observacao") or "—",
            }
            for item in st.session_state.auth_credenciais
        ]
        auth_selection = st.dataframe(
            auth_table_rows,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="auth_table",
        )
        auth_selected_rows = auth_selection.get("selection", {}).get("rows", []) if auth_selection else []

    with auth_toolbar:
        if st.button(":material/add:", key="toolbar_add_auth", help="Cadastrar autenticação"):
            show_add_auth_dialog()
        if st.button(
            ":material/edit:", key="toolbar_edit_auth", help="Editar ou remover autenticação",
            disabled=not auth_selected_rows,
        ):
            show_edit_auth_dialog(auth_selected_rows[0])

elif module == "Tutorial":
    st.markdown(
        '<div class="hero"><div>'
        f'<div class="eyebrow">GestorJus - {html.escape(st.session_state.firm_profile["nome"])}</div>'
        '<h1>Tutorial.</h1>'
        '<div class="lede">Como o GestorJus consulta cada sistema — os três modelos de consulta usados hoje, '
        'e qual órgão/plataforma usa cada um.</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="eyebrow">RESUMO POR PLATAFORMA</div>', unsafe_allow_html=True)
    st.dataframe(
        [
            {"Plataforma": "DJe", "Modelo de consulta": "API", "Situação": "Em produção (DataJud + DJEN)"},
            {"Plataforma": "TCU", "Modelo de consulta": "API + Push", "Situação": "Em produção"},
            {"Plataforma": "TCU (Conecta)", "Modelo de consulta": "Monitoramento assistido · colagem inteligente", "Situação": "Em produção, como complemento ao Push"},
            {"Plataforma": "SEI", "Modelo de consulta": "Monitoramento assistido · link externo", "Situação": "Em produção; colagem/extensão ainda não implementadas"},
            {"Plataforma": "DET", "Modelo de consulta": "API (planejada)", "Situação": "Aguardando credenciais oficiais"},
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown('<div class="eyebrow" style="margin-top:1.6rem;">OS TRÊS MODELOS DE CONSULTA</div>', unsafe_allow_html=True)

    tutorial_tab_api, tutorial_tab_push, tutorial_tab_assistido = st.tabs(
        ["API", "Push", "Monitoramento assistido"]
    )

    with tutorial_tab_api:
        st.markdown(
            "**O que é:** o GestorJus fala diretamente com um endpoint oficial (HTTP/JSON) do órgão e recebe "
            "os dados já estruturados, sob demanda, sem intervenção manual e sem precisar abrir nenhum portal."
        )
        st.markdown(
            "**Onde é usado hoje:** aba DJe (DataJud do CNJ, para movimentações processuais, e DJEN — Diário de "
            "Justiça Eletrônico Nacional, para publicações) e aba TCU (busca pública por número de processo)."
        )
        st.markdown(
            "**Como funciona no app:** ao clicar em \"Consultar movimentações\", o GestorJus monta a requisição "
            "(número CNJ, período, CNPJ/razão social etc.), envia para o endpoint público correspondente e "
            "transforma o JSON de resposta em uma tabela cronológica. Como são APIs públicas, nenhuma senha do "
            "usuário é pedida ou armazenada para esta consulta."
        )
        status(
            "Limitação observada: o DJEN restringe requisições a endereços IP localizados no Brasil. Em um "
            "ambiente hospedado fora do país — como este protótipo — a consulta automática ao DJEN falha; o "
            "GestorJus detecta isso e exibe um aviso explicativo com dados ilustrativos no lugar, em vez de um "
            "erro técnico (veja a aba Monitoramento → DJe). O mesmo código volta a consultar dados reais ao "
            "publicar em um servidor com IP brasileiro.",
            "neutral",
        )

    with tutorial_tab_push:
        st.markdown(
            "**O que é:** em vez do GestorJus ir buscar ativamente, o próprio órgão empurra (\"push\") a "
            "notificação de cada nova movimentação para uma caixa de e-mail cadastrada. O app lê essa caixa e "
            "extrai os dados estruturados de cada mensagem."
        )
        st.markdown(
            "**Onde é usado hoje:** aba TCU, serviço oficial \"Acompanhamento processual (Push)\"."
        )
        st.markdown(
            "**Como funciona no app:** o escritório cadastra, uma única vez e diretamente no site do TCU (login "
            "gov.br), os processos de interesse apontando para o e-mail conectado ao GestorJus em Autenticações. "
            "A partir daí, toda nova movimentação chega automaticamente por e-mail. Ao clicar em \"Sincronizar\", "
            "o GestorJus lê a caixa do Gmail conectado via OAuth, reconhece os e-mails de Acompanhamento "
            "processual e importa data, descrição, relator e interessados de cada movimentação — sem exigir login "
            "no site do TCU a cada consulta."
        )
        status(
            "Pré-requisito: conectar uma conta Google (Gmail) em Autenticações. O cadastro inicial do Push para "
            "cada processo ainda precisa ser feito manualmente, uma vez, no site do TCU.",
            "neutral",
        )

    with tutorial_tab_assistido:
        st.markdown(
            "**O que é:** para sistemas que não têm API pública, a consulta continua começando de forma manual — "
            "abrir o portal do próprio órgão — mas o GestorJus reduz o trabalho de duas formas complementares:"
        )
        st.markdown(
            "1. **Colagem inteligente:** o usuário seleciona e copia o histórico exibido na tela do portal (por "
            "exemplo, a aba HISTÓRICO do Conecta TCU) e cola num campo do GestorJus. Um interpretador reconhece o "
            "padrão \"DD/MM/AAAA HH:MM:SS - descrição\" de cada linha e organiza tudo automaticamente numa tabela, "
            "sem digitação manual.\n"
            "2. **Extensão de navegador (planejada):** uma extensão instalada no navegador do usuário capturaria "
            "automaticamente os dados exibidos na página do portal durante a consulta manual (por exemplo, no "
            "SEI) e os enviaria para o GestorJus — eliminando até a etapa de copiar e colar."
        )
        st.markdown(
            "**Onde é usado hoje:** aba SEI (o app abre o link de acesso externo cadastrado para o processo no "
            "portal do órgão emissor; a colagem inteligente e a extensão ainda não foram implementadas para o "
            "SEI) e aba TCU → Conecta TCU (colagem inteligente já disponível, como complemento ao Push, para "
            "trazer o histórico completo que exige login)."
        )
        status(
            "Limitação: continua exigindo acesso manual ao portal do órgão (com login, quando exigido) e depende "
            "do formato de exportação/tela do próprio portal — mudanças de layout no portal podem exigir ajuste "
            "no interpretador.",
            "neutral",
        )
