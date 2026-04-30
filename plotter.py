import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


def create_control_chart(df_ponto, area_name, ponto_name, limits):
    """
    Gera um gráfico de controle padrão GMP para monitoramento ambiental.
    Garante ausência de grids, fundo branco e linhas de limites bem demarcados.
    """
    # Ordenar por data (Crucial para a linha de tendência não cruzar o gráfico erraticamente)
    df_ponto = df_ponto.sort_values(by="Data")

    # Criar a figura com proporção adequada para relatórios
    fig, ax = plt.subplots(figsize=(10, 5))

    # 1. Plotar a Série de Dados (Linha escura contínua com marcadores circulares pretos)
    ax.plot(
        df_ponto['Data'],
        df_ponto['Resultado'],
        color='red',                 # Cor da linha
        marker='o',                  # Tipo do marcador (círculo)
        markerfacecolor='black',     # Cor de dentro da bolinha
        markeredgecolor='black',     # Cor da borda da bolinha
        linestyle='-',
        linewidth=1.5,
        markersize=6,
        label="Resultado"
    )

    # 2. Extrair os Limites do Dicionário/Series
    lim_alerta = limits.get('Limite Alerta', 0)
    lim_acao = limits.get('Limite Ação', 0)
    lim_espec = limits.get('Especificação Máxima', 0)
    unidade = limits.get('Unidade', 'Valor')

    # Pegar as coordenadas do eixo X para posicionar os rótulos à direita
    x_min, x_max = ax.get_xlim()
    text_x = x_max + (x_max - x_min) * 0.02  # Offset leve para fora do gráfico

    # 3. Desenhar Linhas de Especificação e Rótulos
    # Usamos cores ligeiramente ajustadas em Hex (ex: Gold no lugar de amarelo puro) para garantir contraste no fundo branco.

    # Linha Amarela (Alerta)
    ax.axhline(y=lim_alerta, color='#FFD700', linestyle='--', linewidth=1.5)
    ax.text(text_x, lim_alerta, f"Alerta ≥ {lim_alerta}", color='#D4AF37', va='center', fontweight='bold')

    # Linha Laranja (Ação)
    ax.axhline(y=lim_acao, color='#FF8C00', linestyle='--', linewidth=1.5)
    ax.text(text_x, lim_acao, f"Ação ≥ {lim_acao}", color='#FF8C00', va='center', fontweight='bold')

    # Linha Vermelha (Especificação Máxima)
    ax.axhline(y=lim_espec, color='#FF0000', linestyle='-', linewidth=2)
    ax.text(text_x, lim_espec, f"Espec. Máx. {lim_espec}", color='#FF0000', va='center', fontweight='bold')

    # 4. Formatação de Layout GMP
    ax.set_title(f"Monitoramento - {area_name} - {ponto_name}", fontweight='bold', pad=15)
    ax.set_xlabel("Data da Amostragem", fontweight='bold')
    ax.set_ylabel(unidade, fontweight='bold')

    # Limpeza visual (sem grids, fundo branco)
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    ax.grid(False)

    # Remover bordas superior e direita para um visual laboratorial mais limpo
    ax.spines['top'].set_visible('black')
    ax.spines['right'].set_visible('black')
    ax.spines['bottom'].set_color('black')
    ax.spines['left'].set_color('black')

    # Formatação das Datas no Eixo X
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
    plt.xticks(rotation=45)

    # Ajustar margens para garantir que os textos à direita não sejam cortados
    plt.subplots_adjust(right=0.85, bottom=0.2)

    return fig
