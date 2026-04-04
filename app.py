import streamlit as st
import pandas as pd

# Inicializa banco de dados e migração
from db import init_db, migrate_json_to_db
init_db()
migrate_json_to_db()

# Importação dos módulos especialistas
from auth import require_auth, render_logout_button
from config_manager import load_config, save_config
from analyzer import evaluate_compliance
from plotter import create_control_chart
from report_generator import generate_pdf_bytes

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA ---
st.set_page_config(
    page_title="Sistema SOMA",
    page_icon="\U0001f9ea",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CACHE ---
@st.cache_data(ttl=60)
def _load_config_cached(_counter=0):
    """Cache do load_config com TTL de 60s. Counter força invalidação manual."""
    return load_config()


# --- FUNÇÕES DE LÓGICA ---

def process_data(file, sheet_name):
    """Lê uma aba específica do Excel com tratamento de erros robusto e Data Integrity."""
    try:
        df = pd.read_excel(file, sheet_name=sheet_name)

        if df.empty:
            st.error(f"\u274c A aba '{sheet_name}' está vazia. Verifique a planilha e tente novamente.")
            return None

        df.columns = [str(c).strip().capitalize() for c in df.columns]

        required_cols = ["Ponto", "Data", "Resultado"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"\u274c Erro de Estrutura na aba '{sheet_name}': Faltam colunas: {missing_cols}")
            st.info("Colunas esperadas: 'Ponto', 'Data' e 'Resultado'.")
            return None

        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        if df['Data'].isnull().all():
            st.error("\u274c Erro de Formato: A coluna 'Data' não contém datas válidas.")
            return None

        df['Resultado'] = pd.to_numeric(df['Resultado'], errors='coerce')
        if df['Resultado'].isnull().any():
            linhas_erro = df[df['Resultado'].isnull()].index.tolist()
            st.warning(f"\u26a0\ufe0f Valores não numéricos na coluna 'Resultado' (linhas {linhas_erro}). Dados ignorados.")
            df = df.dropna(subset=['Resultado'])

        df['Resultado'] = df['Resultado'].astype(int)
        return df

    except ValueError as ve:
        st.error(f"\u274c Erro de Leitura: {ve}")
        return None
    except Exception as e:
        st.error(f"\u274c Erro inesperado: {e}")
        return None


# --- INTERFACES ---

def render_config_page():
    """Configurações de áreas — admin edita, viewer apenas lê."""
    st.header("\u2699\ufe0f Configurações de Áreas e Limites")

    is_admin = st.session_state.get("role") == "admin"

    df_config = _load_config_cached()

    st.dataframe(df_config, use_container_width=True, hide_index=True)

    if not is_admin:
        st.info("\U0001f512 Acesso somente leitura. Contate um administrador para alterar limites.")
        return

    st.divider()
    st.subheader("\U0001f512 Edição de Limites")
    st.caption("Todas as alterações são registradas no log de auditoria.")

    edited_df = st.data_editor(
        df_config,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "\u00c1rea/Equipamento": st.column_config.TextColumn("Identificador da Área", required=True),
            "Unidade": st.column_config.TextColumn("Unidade", help="Ex: UFC/placa, UFC/m³, UFC/swab", required=True),
            "Limite Alerta": st.column_config.NumberColumn("Lim. Alerta", min_value=0),
            "Limite A\u00e7\u00e3o": st.column_config.NumberColumn("Lim. Ação", min_value=0),
            "Especifica\u00e7\u00e3o M\u00e1xima": st.column_config.NumberColumn("Espec. Máxima", min_value=0),
        },
    )

    if st.button("Salvar Configurações", type="primary", use_container_width=True):
        save_config(edited_df)
        _load_config_cached.clear()
        st.success("\u2705 Configurações salvas e audit trail registrado!")


def render_audit_log_page():
    """Página de log de auditoria — apenas admin."""
    from db import get_audit_log

    st.header("\U0001f4cb Log de Auditoria")
    st.caption("Histórico de todas as alterações de configuração e ações de login/logout.")

    df_log = get_audit_log()
    if df_log.empty:
        st.info("Nenhuma entrada no log de auditoria.")
        return

    st.dataframe(df_log, use_container_width=True, hide_index=True)

    st.divider()
    col_csv, col_xls = st.columns(2)
    with col_csv:
        csv_bytes = df_log.to_csv(index=False, encoding="utf-8-sig").encode("utf-8")
        st.download_button(
            label="\u2b07\ufe0f Baixar CSV",
            data=csv_bytes,
            file_name="audit_log.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_xls:
        import io
        buf = io.BytesIO()
        df_log.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button(
            label="\u2b07\ufe0f Baixar Excel",
            data=buf,
            file_name="audit_log.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def _render_compliance_panel(df_filtrado, limites, mes_selecionado):
    """Renderiza o bloco de Motor de Alertas e Compliance."""
    st.header("\U0001f6a8 Motor de Alertas e Compliance")
    df_desvios, parecer, cor_parecer = evaluate_compliance(df_filtrado, limites)

    getattr(st, cor_parecer)(f"**Parecer Final Automático:**\n\n{parecer}")

    if not df_desvios.empty:
        st.error(f"\u26a0\ufe0f **{len(df_desvios)}** desvio(s) no mês de {mes_selecionado}:")
        st.dataframe(df_desvios, use_container_width=True)

    return df_desvios


def _render_chart_panel(df_filtrado, area, limites):
    """Renderiza o bloco de gráficos com multiselect de pontos."""
    st.header("\U0001f4c8 Gráficos de Controle")
    pontos_unicos = df_filtrado['Ponto'].unique()

    selected_pontos = st.multiselect(
        "\U0001f50d Selecione os pontos para exibir:",
        options=list(pontos_unicos),
        default=list(pontos_unicos),
    )

    if not selected_pontos:
        st.info("Selecione ao menos um ponto para gerar o gráfico.")
        return {}

    abas = st.tabs([str(pt) for pt in selected_pontos])
    figuras_geradas = {}

    for idx, ponto in enumerate(selected_pontos):
        with abas[idx]:
            df_ponto = df_filtrado[df_filtrado['Ponto'] == ponto].copy()
            fig = create_control_chart(df_ponto, area, ponto, limites)
            st.pyplot(fig)
            figuras_geradas[ponto] = fig

    return figuras_geradas


def render_upload_page():
    """Inserção, processamento, compliance, gráficos e exportação."""
    st.header("\U0001f4ca Inserção e Processamento de Dados")

    df_config = _load_config_cached()
    lista_areas = df_config["\u00c1rea/Equipamento"].tolist()

    if not lista_areas:
        st.warning("\u26a0\ufe0f Nenhuma área configurada. Contate um administrador.")
        return

    uploaded_file = st.file_uploader("Anexe a planilha de monitoramento (.xlsx)", type=["xlsx"])

    if uploaded_file:
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names
        except Exception as e:
            st.error(f"\u274c Erro ao ler as abas: {e}")
            return

        st.divider()
        st.subheader("\U0001f4c2 Seleção de Dados e Área")

        col_sheet, col_area = st.columns(2)

        with col_sheet:
            selected_sheet = st.selectbox("1. Selecione a Aba:", sheet_names)

        with col_area:
            area_final = st.selectbox("2. Selecione a área:", ["---"] + lista_areas)

        if area_final != "---":
            if st.button("Validar e Carregar Dados", type="primary"):
                with st.spinner("Lendo e validando dados..."):
                    df_processado = process_data(uploaded_file, selected_sheet)

                if df_processado is not None:
                    limites = df_config[df_config["\u00c1rea/Equipamento"] == area_final].iloc[0]

                    st.session_state['data_raw'] = df_processado
                    st.session_state['area'] = area_final
                    st.session_state['limits'] = limites
                    st.session_state['pdf_ready'] = False

    # --- FILTRAGEM E RENDERIZAÇÃO ---
    if 'data_raw' in st.session_state:
        df_raw = st.session_state['data_raw']
        area = st.session_state['area']
        limites = st.session_state['limits']

        st.divider()

        st.header("\U0001f4c5 Filtro de Período")

        df_raw['Periodo'] = df_raw['Data'].dt.to_period('M')
        periodos_unicos = df_raw['Periodo'].dropna().unique()
        periodos_ordenados = sorted(periodos_unicos, reverse=True)
        opcoes_meses = [p.strftime('%m/%Y') for p in periodos_ordenados]

        if not opcoes_meses:
            st.error("Sem datas válidas para filtrar.")
            return

        mes_selecionado = st.selectbox("Selecione o Mês/Ano:", opcoes_meses)

        periodo_filtro = pd.Period(mes_selecionado, freq='M')
        df_filtrado = df_raw[df_raw['Periodo'] == periodo_filtro].copy()

        st.info(f"**{mes_selecionado}** ({len(df_filtrado)} registros)")

        if df_filtrado.empty:
            st.warning("Sem dados para este período.")
            return

        st.divider()

        _render_compliance_panel(df_filtrado, limites, mes_selecionado)

        st.divider()

        figuras_geradas = _render_chart_panel(df_filtrado, area, limites)

        st.divider()

        st.header("\U0001f4c4 Exportação de Documentação")
        st.write(f"Relatório PDF referente a **{mes_selecionado}**.")

        col_btn1, col_btn2 = st.columns([1, 2])

        with col_btn1:
            if st.button("\u2699\ufe0f Preparar Relatório PDF", use_container_width=True):
                with st.spinner("Compilando PDF..."):
                    pdf_bytes = generate_pdf_bytes(df_filtrado, area, limites, figuras_geradas)
                    st.session_state['pdf_bytes'] = pdf_bytes
                    st.session_state['pdf_ready'] = True
                    st.success("PDF gerado com sucesso!")

        with col_btn2:
            if st.session_state.get('pdf_ready', False):
                nome_mes = mes_selecionado.replace("/", "_")
                st.download_button(
                    label="\u2b07\ufe0f Baixar Relatório (PDF)",
                    data=st.session_state['pdf_bytes'],
                    file_name=f"Relatorio_{area.replace(' ', '_')}_{nome_mes}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )


# --- ROTEADOR PRINCIPAL ---
def main():
    # Gate de autenticação
    if not require_auth():
        return

    # Usuário logado — renderiza app principal
    render_logout_button()

    st.sidebar.title("\U0001f9eb Sistema SOMA")
    st.sidebar.markdown("Monitoramento Ambiental")
    st.sidebar.caption("v2.0")
    st.sidebar.divider()

    is_admin = st.session_state.get("role") == "admin"

    menu_items = ["\U0001f4ca Inserção de Dados", "\u2699\ufe0f Config. de Especificações"]
    if is_admin:
        menu_items.append("\U0001f4cb Log de Auditoria")

    menu = st.sidebar.radio("Navegação:", menu_items)

    if menu == "\u2699\ufe0f Config. de Especificações":
        render_config_page()
    elif menu == "\U0001f4ca Inserção de Dados":
        render_upload_page()
    elif menu == "\U0001f4cb Log de Auditoria" and is_admin:
        render_audit_log_page()


if __name__ == "__main__":
    main()
