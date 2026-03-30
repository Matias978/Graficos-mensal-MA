import streamlit as st
import pandas as pd
import re

# Importação dos nossos módulos especialistas
from config_manager import load_config, save_config
from analyzer import evaluate_compliance
from plotter import create_control_chart
from report_generator import generate_pdf_bytes

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA ---
st.set_page_config(
    page_title="Sistema MA", 
    page_icon="🧪", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNÇÕES DE LÓGICA E TRATAMENTO DE ERROS ---

def find_area_match(filename, area_list):
    """Busca heurística para vincular o arquivo à área correta."""
    filename_clean = filename.lower()
    for area in area_list:
        if area.lower().strip() in filename_clean:
            return area
    return None

def process_data(file):
    """Lê o Excel com tratamento de erros robusto e Data Integrity."""
    try:
        df = pd.read_excel(file)
        
        # 1. Validação de Arquivo Vazio
        if df.empty:
            st.error("❌ O arquivo enviado está vazio. Verifique a planilha e tente novamente.")
            return None

        # 2. Padronização de Colunas (Remove espaços e capitaliza)
        df.columns = [str(c).strip().capitalize() for c in df.columns]
        
        # 3. Validação de Schema (Colunas obrigatórias)
        required_cols = ["Ponto", "Data", "Resultado"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"❌ Erro de Estrutura: Faltam as seguintes colunas obrigatórias na planilha: {missing_cols}")
            st.info("As colunas esperadas são: 'Ponto', 'Data' e 'Resultado'.")
            return None
            
        # 4. Sanitização de Tipos de Dados
        # Converte Data
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        if df['Data'].isnull().all():
            st.error("❌ Erro de Formato: A coluna 'Data' não contém datas válidas.")
            return None
            
        # Converte Resultado para numérico (transforma textos acidentais em NaN e depois avisa)
        df['Resultado'] = pd.to_numeric(df['Resultado'], errors='coerce')
        if df['Resultado'].isnull().any():
            linhas_erro = df[df['Resultado'].isnull()].index.tolist()
            st.warning(f"⚠️ Aviso: Foram encontrados valores não numéricos na coluna 'Resultado' nas linhas {linhas_erro}. Estes dados foram ignorados no gráfico.")
            df = df.dropna(subset=['Resultado']) # Remove as linhas corrompidas para não quebrar o plot

        return df

    except ValueError as ve:
        st.error(f"❌ Erro de Leitura: O formato do arquivo não é suportado ou está corrompido. Detalhes: {ve}")
        return None
    except Exception as e:
        st.error(f"❌ Ocorreu um erro inesperado ao processar o arquivo. Detalhes: {e}")
        return None

# --- INTERFACES (UI) ---

def render_config_page():
    """Etapa 1: Interface de Configurações."""
    st.header("⚙️ Configurações de Áreas e Limites")
    st.markdown("Defina os **Limites de Alerta e Ação** para validação automática de desvios.")

    df_config = load_config()

    edited_df = st.data_editor(
        df_config,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Área/Equipamento": st.column_config.TextColumn("Identificador da Área", required=True),
            "Unidade": st.column_config.TextColumn("Unidade", help="Digite a unidade. Ex: UFC/placa, UFC/m³, UFC/swab", required=True),
            "Limite Alerta": st.column_config.NumberColumn("Lim. Alerta", min_value=0),
            "Limite Ação": st.column_config.NumberColumn("Lim. Ação", min_value=0),
            "Especificação Máxima": st.column_config.NumberColumn("Espec. Máxima", min_value=0)
        }
    )

    if st.button("Salvar Configurações", type="primary", use_container_width=True):
        save_config(edited_df)
        st.success("✅ Configurações atualizadas e registradas no sistema!")

def render_upload_page():
    """Etapas 2 a 5: Ingestão, Filtro de Mês, Motor de Alertas, Gráficos e Exportação."""
    st.header("📊 Inserção e Processamento de Dados")

    df_config = load_config()
    lista_areas = df_config["Área/Equipamento"].tolist()

    if not lista_areas:
        st.warning("⚠️ Nenhuma área configurada. Vá para 'Configurações de Áreas' primeiro.")
        return

    uploaded_file = st.file_uploader("Anexe a planilha de monitoramento (.xlsx)", type=["xlsx"])

    if uploaded_file:
        col1, col2 = st.columns([1, 1])
        suggested_area = find_area_match(uploaded_file.name, lista_areas)

        with col1:
            st.subheader("🔍 Identificação da Área")
            if suggested_area:
                st.success(f"✅ Área detectada: **{suggested_area}**")
                area_final = st.selectbox("Confirmar Área:", lista_areas, index=lista_areas.index(suggested_area))
            else:
                st.warning("⚠️ Área não identificada pelo nome do arquivo.")
                area_final = st.selectbox("Selecione a área manualmente:", ["---"] + lista_areas)

        if area_final != "---":
            # Botão para iniciar o processamento
            if st.button("Validar e Carregar Dados", type="primary"):
                df_processado = process_data(uploaded_file)
                
                if df_processado is not None:
                    limites = df_config[df_config["Área/Equipamento"] == area_final].iloc[0]
                    
                    # Salva os dados brutos para permitir filtragem posterior sem reprocessar
                    st.session_state['data_raw'] = df_processado
                    st.session_state['area'] = area_final
                    st.session_state['limits'] = limites
                    st.session_state['pdf_ready'] = False # Reseta o estado do PDF

    # ==========================================
    # FLUXO DE FILTRAGEM E RENDERIZAÇÃO
    # ==========================================
    if 'data_raw' in st.session_state:
        df_raw = st.session_state['data_raw']
        area = st.session_state['area']
        limites = st.session_state['limits']

        st.divider()
        
        # --- NOVO: FILTRO DE MÊS ---
        st.header("📅 Filtro de Período")
        
        # Extrai os meses/anos únicos e ordena do mais recente para o mais antigo
        df_raw['Periodo'] = df_raw['Data'].dt.to_period('M')
        periodos_unicos = df_raw['Periodo'].dropna().unique()
        periodos_ordenados = sorted(periodos_unicos, reverse=True)
        opcoes_meses = [p.strftime('%m/%Y') for p in periodos_ordenados]
        
        if not opcoes_meses:
            st.error("Não foram encontradas datas válidas na planilha para gerar o filtro.")
            return
            
        # Selectbox para o usuário escolher o mês
        mes_selecionado = st.selectbox("Selecione o Mês/Ano para o Relatório:", opcoes_meses)
        
        # Filtra o DataFrame para conter APENAS o mês selecionado
        df_filtrado = df_raw[df_raw['Data'].dt.strftime('%m/%Y') == mes_selecionado].copy()
        
        st.info(f"Mostrando dados de: **{mes_selecionado}** (Total de {len(df_filtrado)} registros encontrados)")

        if df_filtrado.empty:
            st.warning("Não há dados para exibir neste mês.")
            return

        st.divider()

        # ETAPA 4: MOTOR DE COMPLIANCE
        st.header("🚨 Motor de Alertas e Compliance")
        df_desvios, parecer, cor_parecer = evaluate_compliance(df_filtrado, limites)
        
        getattr(st, cor_parecer)(f"**Parecer Final Automático:**\n\n{parecer}")
        
        if not df_desvios.empty:
            st.error(f"⚠️ Foram detectados **{len(df_desvios)}** desvio(s) no mês de {mes_selecionado}:")
            st.dataframe(df_desvios, use_container_width=True)

        st.divider()

        # ETAPA 3: GRÁFICOS
        st.header("📈 Gráficos de Controle")
        pontos_unicos = df_filtrado['Ponto'].unique()
        abas = st.tabs([str(pt) for pt in pontos_unicos])
        
        figuras_geradas = {}
        
        for idx, ponto in enumerate(pontos_unicos):
            with abas[idx]:
                df_ponto = df_filtrado[df_filtrado['Ponto'] == ponto].copy()
                fig = create_control_chart(df_ponto, area, ponto, limites)
                st.pyplot(fig)
                figuras_geradas[ponto] = fig

        st.divider()

        # ETAPA 5: INTEGRAÇÃO E PDF
        st.header("📄 Exportação de Documentação Oficial")
        st.write(f"Gere o relatório oficial em PDF referente ao mês de **{mes_selecionado}**.")
        
        col_btn1, col_btn2 = st.columns([1, 2])
        
        with col_btn1:
            if st.button("⚙️ Preparar Relatório PDF", use_container_width=True):
                with st.spinner("Compilando PDF e assinaturas..."):
                    pdf_bytes = generate_pdf_bytes(df_filtrado, area, limites, figuras_geradas)
                    st.session_state['pdf_bytes'] = pdf_bytes
                    st.session_state['pdf_ready'] = True
                    st.success("PDF gerado com sucesso!")
        
        with col_btn2:
            if st.session_state.get('pdf_ready', False):
                nome_mes_arquivo = mes_selecionado.replace("/", "_")
                st.download_button(
                    label="⬇️ Baixar Relatório (PDF)",
                    data=st.session_state['pdf_bytes'],
                    file_name=f"Relatorio_{area.replace(' ', '_')}_{nome_mes_arquivo}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

# --- ROTIADOR PRINCIPAL ---
def main():
    st.sidebar.title("🧫 Gerador de relatório Mensal")
    st.sidebar.markdown("Monitoramento Ambiental")
    st.sidebar.divider()
    
    menu = st.sidebar.radio("Navegação:", ["📊 Inserção de Dados", "⚙️ Configurações de Áreas"])

    if menu == "⚙️ Configurações de Áreas":
        render_config_page()
    elif menu == "📊 Inserção de Dados":
        render_upload_page()

if __name__ == "__main__":
    main()