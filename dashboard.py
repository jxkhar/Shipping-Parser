import streamlit as st
import sqlite3
import pandas as pd
from app import ShippingEngine

# 1. Set page config and apply custom professional styling
st.set_page_config(page_title="Maritime Intelligence Engine", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for a clean, modern dark/blue slate maritime dashboard aesthetic
st.markdown("""
    <style>
    /* Main background theme enhancements */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    /* Style block container blocks */
    div[data-testid="stVerticalBlockBorderContainer"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 24px !important;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }
    /* Customize tabs headers */
    button[data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-size: 16px !important;
        font-weight: 500 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #38bdf8 !important;
        border-bottom-color: #38bdf8 !important;
        font-weight: 700 !important;
    }
    /* Custom header branding rules */
    .main-title {
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #38bdf8, #0ea5e9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #94a3b8 !important;
        font-size: 1.1rem !important;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "shipping_market.db"
engine = ShippingEngine()

def load_data(table_name):
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY timestamp DESC", conn)
        # Drop the row ID and raw text from displaying in the visual dataframes
        if 'id' in df.columns: df = df.drop(columns=['id'])
        if 'raw_text' in df.columns: df = df.drop(columns=['raw_text'])
        return df

# --- HEADER SECTION ---
st.markdown('<p class="main-title">🚢 Maritime Market Intelligence Platform</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Automated Rule-Based Ingestion & Entity Extraction Pipeline</p>', unsafe_allow_html=True)

# --- METRIC CARDS OVERVIEW LAYOUT ---
# Dynamically counts rows to present clean operational statistics cards at the top
try:
    t_count = len(load_data("tonnage_records"))
    vc_count = len(load_data("cargo_vc_records"))
    tc_count = len(load_data("cargo_tc_records"))
except:
    t_count, vc_count, tc_count = 0, 0, 0

m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric(label="⚓ Open Tonnage Tracked", value=t_count, delta="Live Fleet")
with m_col2:
    st.metric(label="📦 Voyage Cargo Requirements (VC)", value=vc_count, delta="Market Orders")
with m_col3:
    st.metric(label="⏳ Time Charter Requirements (TC)", value=tc_count, delta="Term Ingestion")

st.divider()

# --- TWO-COLUMN WORKSPACE AREA ---
col_left, col_right = st.columns([1, 1.5], gap="large")

with col_left:
    st.markdown("### 📥 Stream Ingestion Window")
    st.caption("Paste unstructured emails or position logs to parse and index elements instantly.")
    
    email_input = st.text_area(
        "Raw Text Stream Context Input",
        placeholder="Paste your shipping text stream payload blocks directly here...",
        height=280,
        label_visibility="collapsed"
    )
    
    if st.button("⚡ Execute High-Speed Extraction Pipeline", type="primary", use_container_width=True):
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
                st.success(f"Parsing complete. Extracted and stored {processed_count} data modules successfully!")
                st.rerun()
            else:
                st.warning("Text stream checked, but no new unique maritime patterns matched filters.")
        else:
            st.error("Text input window is empty.")

with col_right:
    st.markdown("### 📊 Structured Output Tables")
    st.caption("Click through tabs to examine parsed database indices.")
    
    tab1, tab2, tab3 = st.tabs(["⚓ Vessels (Tonnage)", "📦 Voyage Cargo (VC)", "⏳ Time Charter (TC)"])
    
    with tab1:
        try:
            df_tonnage = load_data("tonnage_records")
            if not df_tonnage.empty:
                st.dataframe(df_tonnage, use_container_width=True, hide_index=True)
            else: st.info("No vessels currently open in market registry.")
        except: st.info("Database matrix table uninitialized.")
        
    with tab2:
        try:
            df_vc = load_data("cargo_vc_records")
            if not df_vc.empty:
                st.dataframe(df_vc, use_container_width=True, hide_index=True)
            else: st.info("No active Voyage Charter requirements in repository.")
        except: st.info("Database matrix table uninitialized.")
        
    with tab3:
        try:
            df_tc = load_data("cargo_tc_records")
            if not df_tc.empty:
                st.dataframe(df_tc, use_container_width=True, hide_index=True)
            else: st.info("No active Time Charter requirements in repository.")
        except: st.info("Database matrix table uninitialized.")