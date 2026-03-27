import os
import tempfile
import pandas as pd
from fpdf import FPDF

class GMPReport(FPDF):
    def __init__(self, area_name, month_year, limits):
        # Alterado para 'P' (Portrait/Retrato) para acomodar a tabela de resultados e o novo rodapé
        super().__init__(orientation="P", unit="mm", format="A4")
        self.area_name = area_name
        self.month_year = month_year
        self.limits = limits

    def header(self):
        """Cabeçalho simplificado e direto, conforme o modelo."""
        # Título Principal (Nome da Área)
        self.set_font("helvetica", "B", 14)
        self.cell(0, 8, str(self.area_name).upper(), align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Mês / Ano formatado
        self.set_font("helvetica", "B", 12)
        self.cell(0, 6, str(self.month_year).upper(), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        """Rodapé com as assinaturas e o campo 'DATA:' separados em duas linhas."""
        # Posiciona a 30mm do fim da página para garantir espaço para as duas linhas
        self.set_y(-30)
        
        # Largura da página dividida para 3 blocos
        w = self.w / 3.2 
        
        # Linha 1: Nomes / Assinaturas
        self.set_font("helvetica", "B", 9)
        self.cell(w, 5, "Preparado por: __________________", align="L")
        self.cell(w, 5, "Revisado por: __________________", align="L")
        self.cell(w, 5, "Aprovado por: __________________", align="L", new_x="LMARGIN", new_y="NEXT")
        
        # Linha 2: Datas
        self.set_font("helvetica", "", 9)
        self.cell(w, 5, "DATA: ___/___/___", align="L")
        self.cell(w, 5, "DATA: ___/___/___", align="L")
        self.cell(w, 5, "DATA: ___/___/___", align="L", new_x="LMARGIN", new_y="NEXT")
        
        # Paginação
        self.set_y(-10)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")


def get_month_year_ptbr(df):
    """Extrai o período da planilha e converte para Português (Ex: Janeiro de 2026)."""
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


def generate_pdf_bytes(df, area_name, limits, dict_figuras):
    """Gera o PDF com Limites, Tabela de Dados e Gráficos de Tendência."""
    month_year = get_month_year_ptbr(df)
    unidade = limits.get('Unidade', 'UFC/placa')

    pdf = GMPReport(area_name, month_year, limits)
    # Margem inferior de 35mm para garantir que as tabelas não invadam o rodapé de assinaturas
    pdf.set_auto_page_break(auto=True, margin=35) 
    pdf.add_page()
    
    # --- 1. BLOCO DE LIMITES ---
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, "Limites de Especificação:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, f"Limite Alerta: {limits.get('Limite Alerta')} {unidade}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Limite Ação: >= {limits.get('Limite Ação')} {unidade}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Especificação: Máx. {limits.get('Especificação Máxima')} {unidade}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # --- 2. TABELA DE DADOS BRUTOS ---
    pdf.set_font("helvetica", "B", 9)
    col_w = [40, 50, 50] # Largura das colunas
    
    # Calcula a margem esquerda para centralizar a tabela na página (Largura A4 = 210mm)
    margin_left = (210 - sum(col_w)) / 2
    pdf.set_x(margin_left)
    
    # Cabeçalho da Tabela
    pdf.cell(col_w[0], 7, "PONTOS", border=1, align="C", fill=False)
    pdf.cell(col_w[1], 7, "DATA", border=1, align="C", fill=False)
    pdf.cell(col_w[2], 7, f"RESULTADOS ({unidade})", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    
    # Preenchimento dinâmico dos dados
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

    # --- 3. INSERÇÃO DOS GRÁFICOS ---
    temp_files = []
    
    for ponto, fig in dict_figuras.items():
        # Cria uma nova página para cada gráfico para garantir que não fiquem espremidos com a tabela
        pdf.add_page()
        
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        fig.savefig(tmp_file.name, format="png", bbox_inches="tight", dpi=300)
        tmp_file.close()
        temp_files.append(tmp_file.name)
        
        # Título do Gráfico
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 8, f"Gráfico de Tendência - Ponto: {ponto}", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Insere a imagem centralizada (Largura ajustada para 180mm na folha retrato)
        pdf.image(tmp_file.name, x=15, w=180) 
        
    # --- COMPILAÇÃO E LIMPEZA ---
    pdf_bytes = bytes(pdf.output())
    
    for tmp in temp_files:
        try:
            os.remove(tmp)
        except Exception:
            pass
            
    return pdf_bytes