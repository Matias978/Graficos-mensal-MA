"""
config_manager.py — Interface compatível com db.py.
Delega operações de leitura e escrita ao módulo db module.
"""
import streamlit as st
from db import load_config as _db_load_config, save_config as _db_save_config


def load_config():
    """Retorna DataFrame de configurações (delegado para db.py)."""
    return _db_load_config()


def save_config(df):
    """Salva configurações com audit trail via db.py."""
    username = st.session_state.get("username", "unknown")
    _db_save_config(df, username)
