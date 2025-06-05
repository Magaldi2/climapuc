import time
import requests
import jwt  
import json
from dotenv import load_dotenv
import os
load_dotenv()

API_URL = os.getenv("API_URL")
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")

def validar_api_login():
    global api_auth_token_full, token_expiration_time

    # Verifica se tem salvo
    if api_auth_token_full and (token_expiration_time > (time.time() + 60)):
        print(f"Usando token existente (GLOBAL). Válido até: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_expiration_time))}")
        return True
    
    # Verifica se tem salvo
    with open('src/auth.json', 'r') as file:
        data = json.load(file)
        print("Leu json")
        if data['token'] and data['expiresIn'] and (data['expiresIn'] > (time.time() + 60)):
            api_auth_token_full = data['token']
            token_expiration_time = data['expiresIn']
            print(f"Usando token existente (JSON). Válido até: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_expiration_time))}")
            return True

    print(f"Token nao encontrado ou expirado. Realizando login em {API_URL}")
    login_url = f"{API_URL}/login"
    login_payload = {
        "username": API_USERNAME,
        "password": API_PASSWORD
    }

    try:
        response = requests.post(login_url, json=login_payload, timeout=10)
        response.raise_for_status()
        response_header = response.headers

        retrive_token = response_header.get("Authorization")  # token JWT no header

        if retrive_token and retrive_token.lower().startswith("bearer "):
            jwt_token = retrive_token.split(" ", 1)[1]
            # Decodifica o JWT sem verificar assinatura
            payload = jwt.decode(jwt_token, options={"verify_signature": False})
            retrive_exp = payload.get("exp")
        else:
            print("ERRO: Header Authorization não encontrado ou formato inválido.")
            api_auth_token_full = None
            return False

        if retrive_token and isinstance(retrive_token, str) and retrive_exp and isinstance(retrive_exp, (int, float)):
            api_auth_token_full = retrive_token
            token_expiration_time = int(retrive_exp)
            print(f"Login na API externa bem-sucedido.")
            print(f"Token (início): {api_auth_token_full[:15]}...")
            print(f"Expira em: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_expiration_time))}")

            with open('src/auth.json', 'w') as file:
                data = {
                    "expiresIn": token_expiration_time,
                    "token": api_auth_token_full,
                }
                json.dump(data, file, indent=4, ensure_ascii=False)

            return True
        else:
            print("ERRO: Token ou expiração não encontrado no JWT.")
            api_auth_token_full = None
            return False

    except requests.exceptions.HTTPError as http_err:
        error_details = ""
        try:
            error_details = http_err.response.json()
        except ValueError:
            error_details = http_err.response.text
        print(f"Erro HTTP durante login na API externa: {http_err}")
        print(f"Status Code: {http_err.response.status_code}, Detalhes: {error_details}")
        api_auth_token_full = None
        return False
    except requests.exceptions.RequestException as e:
        print(f"Erro de requisição durante login na API externa: {e}")
        api_auth_token_full = None
        return False
            
