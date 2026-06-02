import streamlit as st
import sqlite3
import pandas as pd
import json
from app import ShippingEngine

# =========================================================
# 🛑 PROGRAMMATIC API INTERCEPTOR LAYER (MENTOR REQUIREMENT)
# =========================================================
if "query_params" in dir(st) and st.query_params.get("api") == "true":
    engine = ShippingEngine()
    raw_email = st.query_params.get("email_body", "")
    
    if not raw_email:
        st.json({"status": "error", "message": "Email input stream parameter missing."})
        st.stop()
        
    chunks = engine.segment_and_clean(raw_email)
    response_payload = {"TONNAGE": [], "CARGO_VC": [], "CARGO_TC": []}
    
    for chunk in chunks:
        category = engine.classify(chunk)
        if category in ["TONNAGE", "CARGO_VC", "CARGO_TC"]:
            if category == "TONNAGE": data = engine.parse_tonnage(chunk)
            elif category == "CARGO_VC": data = engine.parse_vc(chunk)
            else: data = engine.parse_tc(chunk)
            response_payload[category].append(data)
            engine.save_to_db(category, data, chunk)
            
    st.json(response_payload)
    st.stop()

# =========================================================
# 🎨 HIGH-AESTHETIC CUSTOM DESIGN SYSTEM (CSS INJECTION)
# =========================================================
st.set_page_config(page_title="Email Segregation Intelligence", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Global Background & Typography Reset */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0b0f19 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    /* Custom Title Typography */
    .brand-title {
        font-size: 2.25rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.05em !important;
        background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px !important;
    }
    
    .brand-subtitle {
        color: #64748b !important;
        font-size: 0.95rem !important;
        font-weight: 500;
        letter-spacing: 0.02em;
        margin-top: -5px !important;
        margin-bottom: 35px !important;
    }

    /* Bespoke Metric Cards Design */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        font-weight: 600 !important;
    }

    /* Custom Floating Card Container Blocks */
    .card-pane {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
    }
    
    .card-header {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: #f1f5f9 !important;
        margin-bottom: 4px !important;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .card-subheader {
        font-size: 0.8rem !important;
        color: #64748b !important;
        margin-bottom: 20px !important;
    }

    /* Custom Input Window Restyling */
    textarea {
        background-color: #030712 !important;
        border: 1px solid #1f2937 !important;
        border-radius: 10px !important;
        color: #e2e8f0 !important;
        font-family: monospace !important;
        font-size: 0.85rem !important;
        padding: 14px !important;
    }
    
    textarea:focus {
        border-color: #06b6d4 !important;
        box-shadow: 0 0 0 1px #06b6d4 !important;
    }

    /* High-Aesthetic Accent Button */
    .stButton>button {
        background: linear-gradient(135deg, #06b6d4 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 4px 12px rgba(6, 182, 212, 0.2) !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(6, 182, 212, 0.35) !important;
    }

    /* Clean Minimalist Custom Tabs */
    button[data-baseweb="tab"] {
        color: #64748b !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        background-color: transparent !important;
        border: none !important;
        padding: 10px 16px !important;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #06b6d4 !important;
        border-bottom: 2px solid #06b6d4 !important;
    }

    /* Hide default streamlit containers design artifacts */
    div[data-testid="stVerticalBlockBorderContainer"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0px !important;
        box-shadow: none !important;
    }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "shipping_market.db"
engine = ShippingEngine()

def load_data(table_name):
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY timestamp DESC", conn)
        if 'id' in df.columns: df = df.drop(columns=['id'])
        if 'raw_text' in df.columns: df = df.drop(columns=['raw_text'])
        return df

# --- BRAND SUB-HEADER SYSTEM ---
st.markdown('<p class="brand-title">Email Segregation Intelligence</p>', unsafe_allow_html=True)
st.markdown('<p class="brand-subtitle">Deterministic Entity Ingestion Platform & Programmatic API Suite</p>', unsafe_allow_html=True)

# --- OVERVIEW PERFORMANCE METRICS ---
try:
    t_count = len(load_data("tonnage_records"))
    vc_count = len(load_data("cargo_vc_records"))
    tc_count = len(load_data("cargo_tc_records"))
except:
    t_count, vc_count, tc_count = 0, 0, 0

m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    with st.container():
        st.markdown('<div class="card-pane">', unsafe_allow_html=True)
        st.metric(label="⚓ Open Tonnage Registry", value=f"{t_count} Vessels")
        st.markdown('</div>', unsafe_allow_html=True)
with m_col2:
    with st.container():
        st.markdown('<div class="card-pane">', unsafe_allow_html=True)
        st.metric(label="📦 Voyage Cargo Indexes (VC)", value=f"{vc_count} Orders")
        st.markdown('</div>', unsafe_allow_html=True)
with m_col3:
    with st.container():
        st.markdown('<div class="card-pane">', unsafe_allow_html=True)
        st.metric(label="⏳ Time Charter Terminals (TC)", value=f"{tc_count} Trips")
        st.markdown('</div>', unsafe_allow_html=True)

# --- WORKSPACE INTERACTION SECTION ---
col_left, col_right = st.columns([1, 1.4], gap="large")

with col_left:
    st.markdown('<div class="card-pane">', unsafe_allow_html=True)
    st.markdown('<p class="card-header">📥 Stream Data Gateway</p>', unsafe_allow_html=True)
    st.markdown('<p class="card-subheader">Inject raw unstructured shipping logs or broker sheets to parse variables instantly.</p>', unsafe_allow_html=True)
    
    email_input = st.text_area(
        "Stream Input",
        placeholder="Paste unstructured shipping payloads directly into this layout field...",
        height=320,
        label_visibility="collapsed"
    )
    
    if st.button("Execute Pipeline Matrix", use_container_width=True):
        if email_input.strip():
            chunks = engine.segment_and_clean(email_input)
            processed_count = 0
            for chunk in chunks:
                category = engine.classify(chunk)
                if category in ["TONNAGE", "CARGO_VC", "CARGO_TC"]:
                    if category == "TONNAGE": data = engine.parse_tonnage(chunk)
                    elif category == "CARGO_VC": data = engine.parse_vc(chunk)
                    else: data = engine.parse_tc(chunk)
                    engine.save_to_db(category, data, chunk)
                    processed_count += 1
            if processed_count > 0:
                st.success(f"Parsing complete. Extracted {processed_count} entities.")
                st.rerun()
            else:
                st.warning("No operational patterns recognized.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="card-pane">', unsafe_allow_html=True)
    st.markdown('<p class="card-header">📊 Database Ledger Index matrices</p>', unsafe_allow_html=True)
    st.markdown('<p class="card-subheader">Relational tabular layout views containing current structural records.</p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["⚓ Open Tonnage", "📦 Voyage Cargo (VC)", "⏳ Time Charter (TC)"])
    
    with tab1:
        try:
            df_tonnage = load_data("tonnage_records")
            if not df_tonnage.empty:
                st.dataframe(df_tonnage, use_container_width=True, hide_index=True)
            else: st.caption("Tonnage directory matrix empty.")
        except: st.caption("Uninitialized schema array.")
        
    with tab2:
        try:
            df_vc = load_data("cargo_vc_records")
            if not df_vc.empty:
                st.dataframe(df_vc, use_container_width=True, hide_index=True)
            else: st.caption("Voyage cargo directory matrix empty.")
        except: st.caption("Uninitialized schema array.")
        
    with tab3:
        try:
            df_tc = load_data("cargo_tc_records")
            if not df_tc.empty:
                st.dataframe(df_tc, use_container_width=True, hide_index=True)
            else: st.caption("Time charter directory matrix empty.")
        except: st.caption("Uninitialized schema array.")
    st.markdown('</div>', unsafe_allow_html=True)
