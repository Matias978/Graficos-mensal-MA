import os
import tempfile
import math
import pandas as pd
from fpdf import FPDF


class GMPReport(FPDF):
    def __init__(self, area_name, month_year, limits):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.area_name = area_name
        self.month_year = month_year
        self.limits = limits

    def header(self):
        """Cabeçalho com logo, limites na direita e título centralizado com quebra automática."""
        
        # --- 0. LOGO DA EMPRESA (Canto Superior Esquerdo) ---
        # Certifique-se de que o arquivo 'logo.png' (ou jpg) está na mesma pasta do código
        logo_path = "logo.png" 
        if os.path.exists(logo_path):
            # Posiciona em X=10 (margem esquerda), Y=10 (margem superior), com largura de 35mm
            self.image(logo_path, x=10, y=10, w=35)

        # --- 1. Limites de Especificação (Canto Superior Direito) ---
        # Desenhamos os limites PRIMEIRO, bem no topo (Y = 10)
        self.set_xy(130, 10)

        unidade = self.limits.get('Unidade', 'UFC/placa')

        self.set_font("helvetica", "B", 8)
        self.cell(70, 4, "Limites de Especificação:", align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_font("helvetica", "", 8)
        self.set_x(130)
        self.cell(70, 4, f"Limite Alerta: >= {self.limits.get('Limite Alerta')} {unidade}", align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_x(130)
        self.cell(70, 4, f"Limite Ação: >= {self.limits.get('Limite Ação')} {unidade}", align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_x(130)
        self.cell(70, 4, f"Especificação: Máx. {self.limits.get('Especificação Máxima')} {unidade}", align="R", new_x="LMARGIN", new_y="NEXT")

        # --- 2. Títulos Centrais ---
        # Como os limites descem até o Y=26, colocamos o título a partir do Y=30
        self.set_y(30)
        self.set_font("helvetica", "B", 14)

        # Usamos multi_cell em vez de cell para que nomes gigantes quebrem de linha sozinhos
        self.multi_cell(0, 6, str(self.area_name).upper(), align="C")

        self.set_font("helvetica", "B", 12)
        # Dá um pequeno espaço e escreve o mês
        self.set_y(self.get_y() + 2)
        self.multi_cell(0, 6, str(self.month_year).upper(), align="C")

        # Dá um respiro final antes de começar a tabela ou gráficos no corpo da página
        self.set_y(self.get_y() + 8)

    def footer(self):
        """Rodapé com as assinaturas e o campo 'DATA:' separados em duas linhas."""
        self.set_y(-30)
        w = self.w / 3.2

        self.set_font("helvetica", "", 9)
        self.cell(w, 5, "Preparado por: __________________", align="L")
        self.cell(w, 5, "Revisado por: __________________", align="L")
        self.cell(w, 5, "Aprovado por: __________________", align="L", new_x="LMARGIN", new_y="NEXT")

        self.set_font("helvetica", "", 9)
        self.cell(w, 5, "DATA: _______/_________/________", align="L")
        self.cell(w, 5, "DATA: _______/_________/________", align="L")
        self.cell(w, 5, "DATA: _______/_________/________", align="L", new_x="LMARGIN", new_y="NEXT")

        self.set_y(-10)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")


def get_month_year_ptbr(df):
    """Extrai o período da planilha e converte para Português."""
    meses = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
             7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}

    if not df.empty and pd.notnull(df['Data'].iloc[0]):
        datas = pd.to_datetime(df['Data'])
        d_min, d_max = datas.min(), datas.max()

        if d_min.month == d_max.month and d_min.year == d_max.year:
            return f"{meses[d_min.month]} de {d_min.year}"
        else:
            return f"{meses[d_min.month]}/{d_min.year} a {meses[d_max.month]}/{d_max.year}"

    return "DATA INDISPONÍVEL"


def _render_data_table(pdf, df, unidade):
    """Renderiza a tabela de dados brutos no PDF."""
    pdf.set_font("helvetica", "B", 9)
    col_w = [40, 50, 50]

    margin_left = (210 - sum(col_w)) / 2
    pdf.set_x(margin_left)

    pdf.cell(col_w[0], 7, "PONTOS", border=1, align="C", fill=False)
    pdf.cell(col_w[1], 7, "DATA", border=1, align="C", fill=False)
    pdf.cell(col_w[2], 7, f"RESULTADOS ({unidade})", border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "", 9)
    for _, row in df.iterrows():
        pdf.set_x(margin_left)
        ponto = str(row['Ponto'])
        data_str = row['Data'].strftime('%d/%m/%Y') if pd.notnull(row['Data']) else ""
        resultado = str(row['Resultado'])

        pdf.cell(col_w[0], 6, ponto, border=1, align="C")
        pdf.cell(col_w[1], 6, data_str, border=1, align="C")
        pdf.cell(col_w[2], 6, resultado, border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)


def render_chart_page(pdf, figuras, start_idx, charts_per_page=2):
    """
    Renderiza uma página com até 2 gráficos, um abaixo do outro.
    Retorna o próximo índice não utilizado.
    """
    img_w = 160
    img_h = 85
    gap = 10

    n_rendered = 0
    i = 0
    while i < charts_per_page and start_idx + i < len(figuras):
        ponto = list(figuras.keys())[start_idx + i]
        fig = list(figuras.values())[start_idx + i]

        # Posiciona verticalmente respeitando o header
        if i == 0:
            pdf.set_y(pdf.get_y() + 15)  # Respiro após o header
        else:
            pdf.set_y(pdf.get_y() + gap)

        # Título do gráfico
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 6, f"Grafico de Tendencia - Ponto: {ponto}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Salva imagem temporária
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", dpi=150)
        tmp_file.close()

        # Insere imagem centralizada
        x = (210 - img_w) / 2
        pdf.image(tmp_file.name, x=x, y=pdf.get_y(), w=img_w)

        # Avança cursor após a imagem
        pdf.set_y(pdf.get_y() + img_h)

        try:
            os.remove(tmp_file.name)
        except Exception:
            pass

        n_rendered += 1
        i += 1

    return start_idx + n_rendered


def generate_pdf_bytes(df, area_name, limits, dict_figuras):
    """Gera o PDF com Limites no cabeçalho, Tabela de Dados e Gráficos de Tendência."""
    month_year = get_month_year_ptbr(df)
    unidade = limits.get('Unidade', 'UFC/placa')

    pdf = GMPReport(area_name, month_year, limits)
    pdf.set_auto_page_break(auto=True, margin=35)
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- 1. TABELA DE DADOS BRUTOS ---
    _render_data_table(pdf, df, unidade)

    # --- 2. INSERÇÃO DOS GRÁFICOS (2 por página) ---
    idx = 0
    charts_per_page = 2

    while idx < len(dict_figuras):
        # Cria nova página para os gráficos
        pdf.add_page()
        idx = render_chart_page(pdf, dict_figuras, idx, charts_per_page=charts_per_page)

    # --- COMPILAÇÃO ---
    pdf_bytes = bytes(pdf.output())

    return pdf_bytes