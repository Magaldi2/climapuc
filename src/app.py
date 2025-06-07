import time
from flask import Flask, jsonify, render_template, send_from_directory, request as flask_request
from multiprocessing import Process  
import mqtt_handler as mqtt_handler
from mqtt_handler import setup_mqtt
import math
import requests
import mysql.connector
from dotenv import load_dotenv
import jwt  
import os
from datetime import datetime, timedelta , timezone
import json
# from auth import validar_api_login
from src.clima import clima_bp

load_dotenv()

app = Flask(
    __name__,
    template_folder='./public/templates',
    static_folder='./public/static'
)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.register_blueprint(clima_bp)


# Configs de login da pagina da constanta
API_URL = os.getenv("API_URL")
API_USERNAME = os.getenv("API_USERNAME")
API_PASSWORD = os.getenv("API_PASSWORD")


api_auth_token_full = None
token_expiration_time = 0

# rotina de login na API da Constanta

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
            
# CHAMADA DAS APIS DAS LUMINARIAS NA API DA CONTANTA
@app.route('/api/luminaires', methods=['GET'])
def get_luminaires():
    if not validar_api_login():
        return jsonify({'error': 'Falha ao autenticar na API externa'}), 401
    url = f"{API_URL}/luminaria"
    headers = {
        "Authorization": api_auth_token_full
    }
    params = {}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        luminarias = response.json()
        return jsonify(luminarias)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar luminárias: {e}")
        return jsonify({'error': 'Erro ao buscar luminárias'}), 500


@app.route('/api/dimmerhistory', methods=['GET'])
def get_dimmer():
    if not validar_api_login():
        return jsonify({'error': 'Falha ao autenticar na API externa'}), 401
    url = f"{API_URL}/historico/dimmer"
    headers = {
        "Authorization": api_auth_token_full
    }
    params = {}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        dimmer = response.json()
        return jsonify(dimmer)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar luminárias: {e}")
        return jsonify({'error': 'Erro ao buscar luminárias'}), 500

@app.route('/api/modem', methods=['GET'])
def get_modems():
    if not validar_api_login():
        return jsonify({'error': 'Falha ao autenticar na API externa'}), 401
    url = f"{API_URL}/modem"
    headers = {
        "Authorization": api_auth_token_full
    }
    params = {}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        modem = response.json()
        return jsonify(modem)
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar modems: {e}")
        return jsonify({'error': 'Erro ao buscar modems'}), 500
    
@app.route('/luminaires')
def luminaires():
    if not validar_api_login():
        return render_template('luminaire.html', luminaires_data=[])

    url = f"{API_URL}/luminaria"
    headers = {"Authorization": api_auth_token_full}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        luminaires_data = []
        for lum in data.get("content", []):
            try:
                lat = float(lum.get("latitude", 0))
                lon = float(lum.get("longitude", 0))
            except (TypeError, ValueError):
                lat, lon = 0, 0
            luminaires_data.append({
                "id": lum.get("id"),
                "name": lum.get("nome") or lum.get("nameLuminaria") or lum.get("descricao") or f"Luminária {lum.get('id')}",
                "lat": lat,
                "lon": lon,
                "status": lum.get("statusLampada") or lum.get("status") or "desconhecido",
                "serial": lum.get("serial"),
                "devEui": lum.get("devEui"),
                "dimmerValue": lum.get("dimmerValue"),
            })
    except Exception as e:
        print(f"Erro ao buscar luminárias reais: {e}")
        luminaires_data = []

    return render_template('luminaire.html', luminaires_data=luminaires_data)

@app.route('/api/state', methods=['POST'])
def on_off_luminaire():
    auth_success = validar_api_login() # Chama sua função de login
    if not auth_success:
        return jsonify({
            "message": "Teste de login na API externa: FALHOU!",
            "token_obtido": False
        }), 500
    
    lamp_serial = flask_request.json.get('lampSerial')
    dimmer_value = flask_request.json.get('dimmerValue')

    if not lamp_serial:
        return jsonify({"error": "lampSerial não informado"}), 400
    if dimmer_value is None:
        return jsonify({"error": "dimmerValue não informado"}), 400
    
    print("auth token", api_auth_token_full)
    if api_auth_token_full is None:
        return jsonify({"error": "Sem auth token"}), 500

    headers = {"Authorization": api_auth_token_full}
    url_luminaria = f"{API_URL}/luminaria/{lamp_serial}"
    try:
        response = requests.get(url_luminaria, headers=headers, timeout=10) 
        response.raise_for_status()
        if response.status_code != 200:
            return jsonify({"error": "Luminária não encontrada"}), 404
        
        url = f"{API_URL}/comando/setsgiipdimmer?lampSerial={lamp_serial}&dimmerValue={dimmer_value}"
        data = response.json()
        lista_de_modems = data.get("listaDeModems", [])

        modems = [modem["devEui"] for modem in lista_de_modems]
        payload = {
            "identifiers": modems
        }
        print(payload)
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            url_force = f"{API_URL}/comando/setforcerelay?lampSerial={lamp_serial}&forceRelay=1"
            response_force = requests.post(url_force, json=payload, headers=headers, timeout=10)
            response_force.raise_for_status()
            
            return jsonify({"message": "Comando enviado com sucesso!"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/static/data/<filename>')
def get_csv(filename):
    base_path = os.path.abspath(os.path.dirname(__file__))
    data_path = os.path.join(base_path, 'public', 'static', 'data')
    return send_from_directory(data_path, filename)


@app.route('/sensor')
def sensor_data():
    return render_template('sensor.html')

# Função para rodar o MQTT em um processo separado
def run_mqtt():
    client = setup_mqtt()
    if client:
        client.loop_forever()
    else:
        print("Erro: Cliente MQTT não foi inicializado corretamente.")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=80)
    validar_api_login()
