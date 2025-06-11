import time
from flask import Flask, jsonify, render_template, send_from_directory, request as flask_request
from multiprocessing import Process
import mqtt_handler as mqtt_handler
from mqtt_handler import setup_mqtt
from mysql.connector import Error # Importar a classe de erro
import math
import requests
import mysql.connector
from dotenv import load_dotenv
import jwt
import os
import datetime
import json
import pandas as pd
import joblib
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
AUTH_JSON = "src/auth.json"
db_config = {
    'host': os.getenv('MYSQL_HOST'),
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE'),
    'port': int(os.getenv('MYSQL_PORT', 3306))
}


api_auth_token_full = None
token_expiration_time = 0

# Constrói o caminho absoluto para o diretório onde este arquivo (app.py) está
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Constrói o caminho completo e absoluto para os arquivos do modelo
MODEL_PATH = os.path.join(BASE_DIR, 'rain_model.joblib')
FEATURES_PATH = os.path.join(BASE_DIR, 'model_features.joblib')

try:
    print(f"Carregando o modelo de previsão de chuva de: {MODEL_PATH}")
    loaded_rain_model = joblib.load(MODEL_PATH)
    print("Modelo carregado com sucesso.")

    print(f"Carregando features do modelo de: {FEATURES_PATH}")
    model_features = joblib.load(FEATURES_PATH)
    print(f"Features que o modelo espera: {model_features}")

except FileNotFoundError:
    print("ERRO CRÍTICO: Arquivos de modelo não encontrados nos caminhos esperados.")
    print("Verifique se 'rain_model.joblib' e 'model_features.joblib' existem na mesma pasta que app.py (dentro de 'src/').")
    print("Execute o script 'train_model.py' primeiro para criar e salvar os arquivos.")
    loaded_rain_model = None
    model_features = None
except Exception as e:
    print(f"Erro inesperado ao carregar o modelo: {e}")
    loaded_rain_model = None
    model_features = None

# rotina de login na API da Constanta

def validar_api_login():
    global api_auth_token_full, token_expiration_time

    # Verifica se tem salvo
    if api_auth_token_full and (token_expiration_time > (time.time() + 60)):
        print(f"Usando token existente (GLOBAL). Válido até: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_expiration_time))}")
        return True

    # Verifica se tem salvo
    if os.path.exists(AUTH_JSON):
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

            with open(AUTH_JSON, 'w') as file:
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

@app.route('/api/luminaires/tickets', methods=["GET"])
def get_luminaires_tickets():
    if not validar_api_login():
        return jsonify({'error': 'Falha ao autenticar na API externa'}), 401
    lamp_serial = flask_request.args.get('lampSerial')
    size = flask_request.args.get('size', 10)
    page = flask_request.args.get('page', 0)
    # status = flask_request.args.get('status', True)

    if not lamp_serial:
        return jsonify({"error": "lampSerial não informado"}), 400

    url = f"{API_URL}/tickets-gelumini/luminaria?serial={lamp_serial}&size={size}&page={page}&status="
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
    luminaire_id = flask_request.args.get('id')
    if not luminaire_id:
        return jsonify({'error': 'Nao achei o Id da luminaira'}), 400

    url = f"{API_URL}/historico/dimmer"
    headers = {
        "Authorization": api_auth_token_full
    }
    params = {
        "id": luminaire_id,
        "size": 1,
        "page": 0,
        "sort": "dtAtualizacao,desc"
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        dimmer = response.json()
        content = dimmer.get("content", [])
        return jsonify(content[0])
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

        # Modems data
        modem_url = f"{API_URL}/modem"
        modem_response = requests.get(modem_url, headers=headers, timeout=10)
        modem_response.raise_for_status()
        modems_data = modem_response.json()

        # Acha o valor do dimmer pelo devEui
        dimmer_by_devEui = {}
        statusBydevEui = {}
        for modem in modems_data.get("content", []):
            deveui = modem.get("devEui")
            dimmer = modem.get("dimmer")
            statusLampada = modem.get("statusLampada")
            if deveui and dimmer is not None:
                dimmer_by_devEui[deveui] = dimmer
            if deveui and statusLampada is not None:
                statusBydevEui[deveui] = statusLampada
        luminaires_data = []
        for lum in data.get("content", []):
            dimmer = None
            dev_eui = None
            for modem in lum.get("listaDeModems", []):
                deveui = modem.get("devEui")
                if deveui in dimmer_by_devEui:
                    dimmer = dimmer_by_devEui[deveui]
                    dev_eui = deveui
                    statusLampada = statusBydevEui.get(deveui, "desconhecido")
                    break
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
                "serial": lum.get("serial"),
                "devEui": dev_eui,
                "dimmer": dimmer,
                "statusLampada" : statusLampada,
                "status": lum.get("status"),
            })
    except Exception as e:
        print(f"Erro ao buscar luminárias reais: {e}")
        luminaires_data = []

    return render_template('luminaire.html', luminaires_data=luminaires_data)

@app.route('/api/state', methods=['POST'])
def on_off_luminaire():
    auth_success = validar_api_login()
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

@app.route('/api/predict/rain_chance')
def predict_rain_chance():
    if not loaded_rain_model:
        return jsonify({"error": "Modelo de previsão não está carregado."}), 503

    latest_data = None
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(host="mysql", user="root", password="example", database="weather_data")
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT temperature, humidity, average_wind_speed FROM sensor_data ORDER BY timestamp DESC LIMIT 1")
        latest_data = cursor.fetchone()
    except Exception as e:
        print(f"Erro ao buscar último dado do MySQL para predição: {e}")
        return jsonify({"error": "Não foi possível obter dados recentes dos sensores."}), 500
    finally:
        if cursor: cursor.close()
        if connection and connection.is_connected(): connection.close()

    if not latest_data:
        return jsonify({"error": "Nenhum dado de sensor encontrado no banco de dados."}), 404

    try:
        current_data_df = pd.DataFrame([latest_data])
        current_data_for_model = current_data_df[model_features]
        probability_of_rain = loaded_rain_model.predict_proba(current_data_for_model)[0][1]

        chance_percent = round(probability_of_rain * 100, 1)

        print(f"Predição de chuva realizada. Chance: {chance_percent}%")

        return jsonify({"chance_de_chuva": chance_percent})

    except Exception as e:
        print(f"Erro durante a predição: {e}")
        return jsonify({"error": "Ocorreu um erro ao gerar a previsão."}), 500
# Rotas do sensor de TEMP, HUM, e CO2
@app.route('/static/data/<filename>')
def get_csv(filename):
    base_path = os.path.abspath(os.path.dirname(__file__))
    data_path = os.path.join(base_path, 'public', 'static', 'data')
    return send_from_directory(data_path, filename)

def get_sql_conn():
    """Cria e retorna uma conexão com o banco de dados usando a configuração global."""
    conexao = None
    try:
        print(db_config)
        conexao = mysql.connector.connect(**db_config)
        if conexao.is_connected():
            print(f"Conexão com o banco de dados '{db_config['database']}' estabelecida com sucesso!")
            return conexao
    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None
    
@app.route('/sensor')
def sensor_data():
    return render_template('sensor.html')

@app.route('/api/luminaire/<lamp_serial>')
def get_luminaire_data(lamp_serial):
    conn = None
    try:
        conn = get_sql_conn()
        if not conn:
            # Usar um log aqui seria ideal em produção
            print("FALHA NA ROTA: Não foi possível conectar ao banco de dados.")
            return jsonify({"error": "Erro interno do servidor"}), 500

        # Usar 'with' garante que o cursor seja fechado automaticamente
        # A MÁGICA ACONTECE AQUI: dictionary=True
        with conn.cursor(dictionary=True) as cursor:
            luminaire_query = "SELECT * FROM luminaires WHERE serial_number = %s"
            cursor.execute(luminaire_query, (lamp_serial,))

            luminaire = cursor.fetchone()

            if not luminaire:
                return jsonify({"error": "Luminaria nao encontrada"}), 404
            
            query = "SELECT * FROM luminaire_data WHERE luminaire_id = %s ORDER BY recorded_at DESC"
            cursor.execute(query, (luminaire['id'],))
            
            resultado = cursor.fetchall()

            resultado_formatado = []
            for row in resultado:
                if 'recorded_at' in row and isinstance(row['recorded_at'], datetime.datetime):
                    row['recorded_at'] = row['recorded_at'].isoformat()
                resultado_formatado.append(row)

            return jsonify({"data": resultado_formatado})
            
    except mysql.connector.Error as e:
        print(f"ERRO DE BANCO DE DADOS: {e}")
        return jsonify({"error": "Erro ao consultar os dados"}), 500
    except Exception as e:
        print(f"ERRO INESPERADO: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado"}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("Conexão com o banco de dados fechada.")


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
