import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "soma.db"


def get_db():
    """Retorna conexão SQLite com row_factory dict-like."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria tabelas se não existirem. Idempotente."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT UNIQUE NOT NULL,
            unidade TEXT NOT NULL DEFAULT '',
            limite_alerta INTEGER DEFAULT 0,
            limite_acao INTEGER DEFAULT 0,
            especificacao_max INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            old_value TEXT,
            new_value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(username);
    """)
    conn.commit()
    conn.close()


def migrate_json_to_db():
    """Se config.json existe, migra para SQLite e renomeia para .bak."""
    config_file = "config.json"
    if not os.path.exists(config_file):
        return False

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        # Arquivo corrompido — não migra
        return False

    conn = get_db()
    for entry in data:
        conn.execute(
            """INSERT OR REPLACE INTO config (area, unidade, limite_alerta, limite_acao, especificacao_max)
               VALUES (?, ?, ?, ?, ?)""",
            (
                entry.get("Área/Equipamento", ""),
                entry.get("Unidade", ""),
                entry.get("Limite Alerta", 0),
                entry.get("Limite Ação", 0),
                entry.get("Especificação Máxima", 0),
            ),
        )

    conn.commit()
    conn.close()

    # Renomeia para backup
    os.rename(config_file, config_file + ".bak")
    return True


def load_config():
    """Retorna DataFrame com configurações de áreas (mesma assinatura do config_manager antigo)."""
    import pandas as pd

    init_db()
    conn = get_db()
    rows = conn.execute("SELECT area, unidade, limite_alerta, limite_acao, especificacao_max FROM config ORDER BY area").fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["Área/Equipamento", "Unidade", "Limite Alerta", "Limite Ação", "Especificação Máxima"])

    df = pd.DataFrame(rows, columns=["Área/Equipamento", "Unidade", "Limite Alerta", "Limite Ação", "Especificação Máxima"])
    return df


def save_config(df, username):
    """Salva DataFrame completo no SQLite (DELETE + INSERT) com audit trail."""
    init_db()
    conn = get_db()

    # Captura valores antigos para auditoria
    old_rows = conn.execute("SELECT area, limite_alerta, limite_acao, especificacao_max FROM config ORDER BY area").fetchall()
    old_map = {r["area"]: dict(r) for r in old_rows}

    now = datetime.now().isoformat()

    # Limpa e reinsere
    conn.execute("DELETE FROM config")

    for _, row in df.iterrows():
        area = row.get("Área/Equipamento", "")
        conn.execute(
            """INSERT OR REPLACE INTO config (area, unidade, limite_alerta, limite_acao, especificacao_max)
               VALUES (?, ?, ?, ?, ?)""",
            (
                area,
                row.get("Unidade", ""),
                row.get("Limite Alerta", 0),
                row.get("Limite Ação", 0),
                row.get("Especificação Máxima", 0),
            ),
        )

        # Auditoria: compara com valores antigos
        old = old_map.get(area)
        new_vals = {
            "Limite Alerta": int(row.get("Limite Alerta", 0)),
            "Limite Ação": int(row.get("Limite Ação", 0)),
            "Especificação Máxima": int(row.get("Especificação Máxima", 0)),
        }

        if old:
            old_vals = {"Limite Alerta": old["limite_alerta"], "Limite Ação": old["limite_acao"], "Especificação Máxima": old["especificacao_max"]}
            if new_vals == old_vals:
                continue
            action = "CONFIG_UPDATE"
            old_json = json.dumps(old_vals, ensure_ascii=False)
        else:
            action = "CONFIG_CREATE"
            old_json = "N/A"

        new_json = json.dumps(new_vals, ensure_ascii=False)

        conn.execute(
            """INSERT INTO audit_log (timestamp, username, action, table_name, record_id, old_value, new_value)
               VALUES (?, ?, ?, 'config', NULL, ?, ?)""",
            (now, username, action, old_json, new_json),
        )

    # Detecta remoções (áreas que existiam antes e não estão mais no df)
    new_areas = set(df["Área/Equipamento"].tolist())
    for old_area in old_map:
        if old_area not in new_areas:
            conn.execute(
                """INSERT INTO audit_log (timestamp, username, action, table_name, record_id, old_value, new_value)
                   VALUES (?, ?, 'CONFIG_DELETE', 'config', NULL, ?, 'Removido')""",
                (now, username, json.dumps(old_map[old_area], ensure_ascii=False)),
            )

    conn.commit()
    conn.close()


def log_audit(username, action, table_name, record_id=None, old_value=None, new_value=None):
    """Insere entrada genérica no audit_log (apend-only)."""
    init_db()
    conn = get_db()
    conn.execute(
        """INSERT INTO audit_log (timestamp, username, action, table_name, record_id, old_value, new_value)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), username or "unknown", action, table_name, record_id, old_value, new_value),
    )
    conn.commit()
    conn.close()


def get_audit_log():
    """Retorna DataFrame com log de auditoria completo."""
    import pandas as pd

    init_db()
    conn = get_db()
    rows = conn.execute("SELECT timestamp, username, action, table_name, old_value, new_value FROM audit_log ORDER BY timestamp DESC").fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame(columns=["Data/Hora", "Usuário", "Ação", "Tabela", "Valor Anterior", "Valor Novo"])

    columns = ["Data/Hora", "Usuário", "Ação", "Tabela", "Valor Anterior", "Valor Novo"]
    return pd.DataFrame(rows, columns=columns)
