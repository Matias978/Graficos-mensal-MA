import numpy as np
import pandas as pd


def evaluate_compliance(df, limits):
    """
    Avalia os resultados contra os limites normativos (Alerta, Ação, Especificação).
    Retorna um DataFrame apenas com os desvios e o Status Final do Lote/Área.
    Usa operações vetorializadas (np.select) ao invés de iterrows.
    """
    lim_alerta = limits.get('Limite Alerta', 0)
    lim_acao = limits.get('Limite Ação', 0)
    lim_espec = limits.get('Especificação Máxima', 0)

    df = df.copy()

    # Pré-formata datas
    df['Data_str'] = df['Data'].apply(
        lambda d: d.strftime('%d/%m/%Y') if pd.notnull(d) else "Data Inválida"
    )

    # Classificação vetorial (do mais crítico ao menos crítico)
    conditions = [
        df['Resultado'] >= lim_espec,
        df['Resultado'] >= lim_acao,
        df['Resultado'] >= lim_alerta,
    ]
    choices_class = [
        'Fora de Especificação (OOS)',
        'Limite de Ação Excedido',
        'Limite de Alerta Excedido',
    ]
    choices_sev = [
        '🔴 Crítico',
        '🟠 Alta',
        '🟡 Moderada',
    ]

    df['Classificação'] = np.select(conditions, choices_class, default='Conforme')
    df['Severidade'] = np.select(conditions, choices_sev, default='')

    # Isola desvios
    mask_desvio = df['Classificação'] != 'Conforme'
    df_desvios = df.loc[mask_desvio, ['Data_str', 'Ponto', 'Resultado', 'Classificação', 'Severidade']].copy()
    df_desvios.rename(columns={'Data_str': 'Data'}, inplace=True)

    # Severidade máxima
    severity_order = {'Fora de Especificação (OOS)': 3, 'Limite de Ação Excedido': 2, 'Limite de Alerta Excedido': 1}
    status_critico = 0
    if not df_desvios.empty:
        max_class = df_desvios['Classificação'].map(severity_order).max()
        status_critico = int(max_class) if pd.notna(max_class) else 0

    # Parecer Final
    if status_critico == 0:
        parecer = "✅ APROVADO - Todos os resultados encontram-se dentro das especificações normativas."
        cor_parecer = "success"
    elif status_critico == 1:
        parecer = "⚠️ ATENÇÃO - Resultados acima do Limite de Alerta detectados. Recomenda-se monitoramento de tendência."
        cor_parecer = "warning"
    elif status_critico == 2:
        parecer = "🛑 AÇÃO REQUERIDA - Limite de Ação excedido. Necessária investigação da causa raiz e possível sanitização."
        cor_parecer = "error"
    else:
        parecer = "❌ REPROVADO (OOS) - Resultados fora da Especificação Máxima. Abrir desvio na Garantia da Qualidade imediatamente."
        cor_parecer = "error"

    return df_desvios, parecer, cor_parecer
