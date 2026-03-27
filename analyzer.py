import pandas as pd

def evaluate_compliance(df, limits):
    """
    Avalia os resultados contra os limites normativos (Alerta, Ação, Especificação).
    Retorna um DataFrame apenas com os desvios e o Status Final do Lote/Área.
    """
    lim_alerta = limits.get('Limite Alerta', 0)
    lim_acao = limits.get('Limite Ação', 0)
    lim_espec = limits.get('Especificação Máxima', 0)
    
    desvios = []
    status_critico = 0 # 0: Aprovado, 1: Alerta, 2: Ação, 3: OOS (Out of Specification)
    
    for _, row in df.iterrows():
        res = row['Resultado']
        ponto = row['Ponto']
        # Tratamento de data para exibição
        data_str = row['Data'].strftime('%d/%m/%Y') if pd.notnull(row['Data']) else "Data Inválida"
        
        # Avaliação Hierárquica (do mais crítico para o menos crítico)
        if res >= lim_espec:
            desvios.append({
                'Data': data_str, 'Ponto': ponto, 'Resultado': res, 
                'Classificação': 'Fora de Especificação (OOS)', 'Severidade': '🔴 Crítico'
            })
            status_critico = max(status_critico, 3)
            
        elif res >= lim_acao:
            desvios.append({
                'Data': data_str, 'Ponto': ponto, 'Resultado': res, 
                'Classificação': 'Limite de Ação Excedido', 'Severidade': '🟠 Alta'
            })
            status_critico = max(status_critico, 2)
            
        elif res >= lim_alerta:
            desvios.append({
                'Data': data_str, 'Ponto': ponto, 'Resultado': res, 
                'Classificação': 'Limite de Alerta Excedido', 'Severidade': '🟡 Moderada'
            })
            status_critico = max(status_critico, 1)

    # Determinação do Parecer Final
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
        
    df_desvios = pd.DataFrame(desvios) if desvios else pd.DataFrame(columns=['Data', 'Ponto', 'Resultado', 'Classificação', 'Severidade'])
    
    return df_desvios, parecer, cor_parecer