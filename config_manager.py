import json
import os
import pandas as pd

CONFIG_FILE = "config.json"

def load_config():
    """Lê o arquivo JSON e retorna um DataFrame para o Streamlit."""
    if not os.path.exists(CONFIG_FILE):
        # Schema inicial padrão para o setor farmacêutico
        initial_data = [
            {
                "Área/Equipamento": "Sala Limpa Grau A",
                "Unidade": "UFC/placa",
                "Limite Alerta": 1,
                "Limite Ação": 1,
                "Especificação Máxima": 1
            }
        ]
        save_config(initial_data)
        return pd.DataFrame(initial_data)
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return pd.DataFrame(data)

def save_config(df_or_list):
    """Salva os dados de configuração de volta no JSON."""
    if isinstance(df_or_list, pd.DataFrame):
        data = df_or_list.to_dict(orient="records")
    else:
        data = df_or_list
        
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)