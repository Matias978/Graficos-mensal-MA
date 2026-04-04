"""
Script utilitário para gerar hash bcrypt de senha.
Uso: python generate_hash.py sua_senha

Saída: copie o hash gerado para o arquivo .streamlit/secrets.toml
"""
import sys
import bcrypt

if len(sys.argv) < 2:
    # Modo interativo
    from getpass import getpass
    password = getpass("Senha: ")
else:
    password = sys.argv[1]

salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
print(f"\nHash bcrypt: {hashed.decode()}")
print("\nCole no .streamlit/secrets.toml como:")
print(f'  password_hash = "{hashed.decode()}"')
