import streamlit as st
import bcrypt


def _get_users():
    """Lê usuários do secrets.toml. Retorna dict {username: {password_hash, role}}."""
    users_data = st.secrets.get("users", [])
    result = {}
    for u in users_data:
        result[u["username"]] = {"password_hash": u["password_hash"], "role": u.get("role", "viewer")}
    return result


def authenticate(username, password):
    """Verifica credenciais contra st.secrets. Retorna dict ou None."""
    users = _get_users()
    user = users.get(username)
    if not user:
        return None
    try:
        if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            return {"username": username, "role": user["role"]}
    except Exception:
        pass
    return None


def render_login():
    """Tela de login que bloqueia todo o restante do app."""
    st.set_page_config(page_title="SOMA - Login", page_icon="\U0001f9ea", layout="centered")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("\U0001f9eb Sistema SOMA")
        st.caption("Sistema Otimizado de Monitoramento Ambiental")
        st.divider()

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("\U0001f464 Usu\u00e1rio", autocomplete="username")
            password = st.text_input("\U0001f512 Senha", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Preencha usu\u00e1rio e senha.")
                    return

                result = authenticate(username, password)
                if result:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = result["username"]
                    st.session_state["role"] = result["role"]
                    st.success(f"Bem-vindo, **{result['username']}**!")
                    st.rerun()
                else:
                    st.error("Usu\u00e1rio ou senha inv\u00e1lidos.")
                    from db import log_audit
                    log_audit(username or "unknown", "LOGIN_FAILED", "users")

    st.divider()
    st.caption("\U0001f510 Acesso restrito a usu\u00e1rios autorizados.")


def require_auth():
    """Se n\u00e3o autenticado, mostra login e para a execu\u00e7\u00e3o.
    Retorna True se j\u00e1 est\u00e1 logado."""
    if st.session_state.get("authenticated"):
        return True

    render_login()
    return False


def render_logout_button():
    """Mostra bot\u00e3o de sair na sidebar com info do usu\u00e1rio."""
    from db import log_audit

    role_badges = {"admin": "\U0001f512 Admin", "viewer": "\U0001f441\ufe0f Viewer"}
    badge = role_badges.get(st.session_state.get("role", ""), "")

    st.sidebar.divider()
    st.sidebar.success(f"\U0001f464 **{st.session_state['username']}** {badge}")

    if st.sidebar.button("\U0001f6aa Sair", use_container_width=True):
        log_audit(st.session_state["username"], "LOGOUT", "users")
        for key in ["authenticated", "username", "role", "data_raw", "area", "limits", "pdf_ready", "pdf_bytes"]:
            st.session_state.pop(key, None)
        st.rerun()
