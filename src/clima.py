import time
import math
import mysql.connector
from flask import Blueprint, render_template, jsonify, send_from_directory
from datetime import datetime, timedelta , timezone

clima_bp = Blueprint('clima', __name__, template_folder='templates', static_folder='static')

def rad_to_direction_with_icon(rad):
    """Converte radianos para direção cardeal e retorna ícone correspondente."""
    directions = [
        ('Norte', 'rotate-0'),
        ('Nordeste', 'rotate-45'),
        ('Leste', 'rotate-90'),
        ('Sudeste', 'rotate-135'),
        ('Sul', 'rotate-180'),
        ('Sudoeste', 'rotate-225'),
        ('Oeste', 'rotate-270'),
        ('Noroeste', 'rotate-315')
    ]
    rad = rad % (2 * math.pi)
    index = int((rad + math.pi / 8) // (math.pi / 4)) % 8
    return directions[index]

def get_rain_status(current_rain_level, previous_rain_level):
    """Determina o status da chuva com base na diferença do nível acumulado."""
    rain_difference = current_rain_level - previous_rain_level
    if rain_difference <= 0:
        return "Não está chovendo"
    elif rain_difference < 0.0006:
        return "Chuviscando"
    else:
        return "Chovendo"

def get_wind_speed_status(wind_speed_kmh):
    """Determina o status da velocidade do vento em km/h baseado na Escala Modificada de Beaufort."""
    if wind_speed_kmh == 0:
        return "Sem vento"
    elif wind_speed_kmh < 12.0:
        return "Brisa leve"
    elif wind_speed_kmh < 20.0:
        return "Vento fresco"
    elif wind_speed_kmh < 41.0:
        return "Vento moderado"
    elif wind_speed_kmh < 62.0:
        return "Vento forte"
    elif wind_speed_kmh < 75.0:
        return "Vento muito forte"
    elif wind_speed_kmh < 103.0:
        return "Vendaval severo"
    elif wind_speed_kmh < 120.0:
        return "Tempestade"
    else:
        return "Ciclone tropical"

def get_uv_status(uv_index):
    """Determina o status da radiação UV."""
    if uv_index < 3:
        return "Níveis baixos de UV"
    elif uv_index < 6:
        return "Níveis moderados de UV"
    elif uv_index < 8:
        return "Níveis altos de UV"
    elif uv_index < 11:
        return "Níveis muito altos de UV"
    else:
        return "Risco extremo de UV"

def get_humidity_status(humidity):
    """Determina o status da umidade."""
    if humidity < 30:
        return "Ar muito seco"
    elif humidity < 60:
        return "Umidade confortável"
    else:
        return "Ar muito úmido"

def get_temperature_status(temperature):
    """Determina o status da temperatura."""
    if temperature < 10:
        return "Frio intenso"
    elif temperature < 20:
        return "Clima frio"
    elif temperature < 25:
        return "Clima agradável"
    elif temperature < 30:
        return "Clima quente"
    else:
        return "Calor extremo"

def calculate_heat_index(temp_c, humidity):
    """Calcula o índice de calor (heat index) em Celsius."""
    if temp_c <= 26.7 or humidity <= 40:
        return temp_c
    T_f = (temp_c * 9/5) + 32
    RH = humidity
    HI_f = -42.379 + 2.04901523 * T_f + 10.14333127 * RH \
           - 0.22475541 * T_f * RH - 0.00683783 * T_f**2 \
           - 0.05481717 * RH**2 + 0.00122874 * T_f**2 * RH \
           + 0.00085282 * T_f * RH**2 - 0.00000199 * T_f**2 * RH**2
    HI_c = (HI_f - 32) * 5/9
    return HI_c

def calculate_wind_chill(temp_c, wind_speed_kmh):
    """Calcula o wind chill (sensação térmica por vento) em Celsius."""
    # Só faz sentido para temperaturas <= 10°C e vento >= 4.8 km/h
    if temp_c > 10 or wind_speed_kmh < 4.8:
        return temp_c
    v = wind_speed_kmh
    wc = 13.12 + 0.6215 * temp_c - 11.37 * v**0.16 + 0.3965 * temp_c * v**0.16
    return wc

def calculate_feels_like(temp_c, humidity, wind_speed_kmh):
    if temp_c <= 10 and wind_speed_kmh >= 4.8:
        return calculate_wind_chill(temp_c, wind_speed_kmh)
    elif temp_c >= 27 and humidity >= 40:
        return calculate_heat_index(temp_c, humidity)
    else:
        return temp_c

def get_daily_temp_stats():
    """Busca apenas as temperaturas Mínima e Máxima do dia atual."""
    connection = None
    cursor = None
    stats = {'min_temp': 0, 'max_temp': 0}
    try:
        connection = mysql.connector.connect(host="mysql", user="root", password="example", database="weather_data")
        cursor = connection.cursor(dictionary=True)

        now_utc = datetime.now(timezone.utc)
        local_now = now_utc - timedelta(hours=3)
        start_of_day = datetime(local_now.year, local_now.month, local_now.day, tzinfo=timezone.utc)
        start_timestamp = int(start_of_day.timestamp()) + 3 * 3600
        end_timestamp = int((start_of_day + timedelta(days=1)).timestamp()) + 3 * 3600

        query = "SELECT MIN(temperature) as min_temp, MAX(temperature) as max_temp FROM sensor_data WHERE timestamp BETWEEN %s AND %s"
        cursor.execute(query, (start_timestamp, end_timestamp))
        result = cursor.fetchone()

        if result and result['min_temp'] is not None:
            stats['min_temp'] = result['min_temp']
            stats['max_temp'] = result['max_temp']

    except mysql.connector.Error as e:
        print(f"Erro ao buscar estatísticas diárias do MySQL: {e}")
    finally:
        if cursor: cursor.close()
        if connection and connection.is_connected(): connection.close()

    return stats

def get_mysql_data():
    """Buscar os dois últimos dados do MySQL."""
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host="mysql",  # Nome do serviço MySQL no Docker Compose
            user="root",
            password="example",
            database="weather_data"
        )
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 2")
        result = cursor.fetchall()
        if len(result) >= 2:
            return result[0], result[1]
        elif len(result) == 1:
            return result[0], None
        else:
            return None, None
    except mysql.connector.Error as e:
        print(f"Erro ao buscar dados do MySQL: {e}")
        return None, None
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()



# Em src/clima.py

@clima_bp.route('/')
def index():
    current_data, previous_data = get_mysql_data()

    if not current_data:
        return render_template('index.html', temperature=0, humidity=0, rain_level=0, wind_speed_kmh=0, wind_direction="N/D", uv_index=0, temperature_status="N/A", humidity_status="N/A", rain_status="N/A", wind_speed_status="N/A", uv_status="N/A", max_temp=0, min_temp=0, feels_like_temp=0)

    daily_stats = get_daily_temp_stats()
    min_temp = daily_stats.get('min_temp', 0)
    max_temp = daily_stats.get('max_temp', 0)

    temperature = current_data.get('temperature', 0)
    humidity = current_data.get('humidity', 0)

    wind_direction_rad = float(current_data.get('wind_direction', 0))
    uv_index = float(current_data.get('uv_index', 0))
    current_rain_level = float(current_data.get('rain_level', 0))
    average_wind_speed = float(current_data.get('average_wind_speed', 0))
    previous_rain_level = float(previous_data.get('rain_level', 0)) if previous_data else current_rain_level
    wind_direction, _ = rad_to_direction_with_icon(wind_direction_rad)
    average_wind_speed_kmh = average_wind_speed * 3.6
    feels_like_temp = calculate_feels_like(temperature, humidity, average_wind_speed_kmh)

    return render_template(
        'index.html',
        temperature=temperature,
        humidity=humidity,
        rain_level=current_rain_level,
        wind_speed_kmh=average_wind_speed_kmh,
        wind_direction=wind_direction,
        uv_index=uv_index,
        temperature_status=get_temperature_status(temperature),
        humidity_status=get_humidity_status(humidity),
        rain_status=get_rain_status(current_rain_level, previous_rain_level),
        wind_speed_status=get_wind_speed_status(average_wind_speed_kmh),
        uv_status=get_uv_status(uv_index),
        max_temp=max_temp,
        min_temp=min_temp,
        feels_like_temp=feels_like_temp
    )



@clima_bp.route('/dados', methods=['GET'])
def dashboard():
    """Rota principal para exibir o dashboard com gráficos interativos."""
    try:
        # Conexão com o MySQL
        connection = mysql.connector.connect(
            host="mysql",  # Nome do serviço MySQL no Docker Compose
            user="root",
            password="example",
            database="weather_data"
        )
        cursor = connection.cursor(dictionary=True)

        # Calcular o início e fim do dia UTC-3
        now = datetime.now(timezone.utc)
        local_now = now - timedelta(hours=3) # Ajuste para UTC-3
        start_of_day = datetime(local_now.year, local_now.month, local_now.day, tzinfo=timezone.utc)
        start_timestamp = int(start_of_day.timestamp()) + 3 * 3600
        end_timestamp = int((start_of_day + timedelta(days=1)).timestamp()) + 3 * 3600

        # Buscar apenas os dados do dia atual ajustado para UTC-3
        query = """
            SELECT timestamp, temperature, humidity, rain_level, average_wind_speed
            FROM sensor_data
            WHERE temperature IS NOT NULL
            AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp
        """
        cursor.execute(query, (start_timestamp, end_timestamp))
        data = cursor.fetchall()
    except mysql.connector.Error as e:
        print(f"Erro ao buscar dados do MySQL: {e}")
        return jsonify({"message": "Erro ao buscar dados do MySQL"}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    if not data:
        return render_template('dashboard.html', message="Nenhum dado disponível no momento.")

    sensor_data = {"temperature": [], "humidity": [], "rain_level": [], "wind_speed": [],"timestamps": []}
    for row in data:
        timestamp = row["timestamp"]
        if timestamp:
            formatted_time = time.strftime('%H:%M', time.localtime(timestamp - 3 * 3600))
            sensor_data["timestamps"].append(formatted_time)
        sensor_data["temperature"].append(row["temperature"])
        sensor_data["humidity"].append(row["humidity"])
        sensor_data["rain_level"].append(row["rain_level"])
        sensor_data["wind_speed"].append(row["average_wind_speed"] * 3.6)  # Adicionando a velocidade média do vento

    return render_template('dashboard.html', sensor_data=sensor_data)

@clima_bp.route('/temperatura', methods=['GET'])
def plot_data():
    try:
        # Conexão com o MySQL
        connection = mysql.connector.connect(
            host="mysql",  # Nome do serviço MySQL no Docker Compose
            user="root",
            password="example",
            database="weather_data"
        )
        cursor = connection.cursor(dictionary=True)

        # Calcular o início e fim do dia UTC-3
        now = datetime.now(timezone.utc)
        local_now = now - timedelta(hours=3) # Ajuste para UTC-3
        start_of_day = datetime(local_now.year, local_now.month, local_now.day, )
        start_timestamp = int(start_of_day.timestamp()) + 3 * 3600
        end_timestamp = int((start_of_day + timedelta(days=1)).timestamp()) + 3 * 3600


        # Buscar apenas os dados do dia atual ajustado para UTC-3
        query = """
            SELECT * FROM sensor_data
            WHERE temperature IS NOT NULL
            AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp
        """
        cursor.execute(query, (start_timestamp, end_timestamp))
        data = cursor.fetchall()

    except mysql.connector.Error as e:
        print(f"Erro ao buscar dados do MySQL: {e}")
        return jsonify({"message": "Erro ao buscar dados do MySQL"}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    if not data:
        return jsonify({"message": "Nenhum dado disponível para o dia atual"}), 404

    # Extrair timestamps e valores de temperatura
    timestamps, values = [], []
    for row in data:
        timestamp = row.get('timestamp')
        temperature = row.get('temperature')
        if timestamp and temperature is not None:
            # Ajustar horário para UTC-3
            adjusted_time = time.strftime('%H:%M', time.localtime(timestamp - 3 * 3600))
            timestamps.append(adjusted_time)
            values.append(float(temperature))

    if not values:
        return jsonify({"message": "Nenhum dado de temperatura disponível para o dia atual"}), 404

    # Calcular métricas (última, média, máxima e mínima)
    last_temperature = values[-1]
    average_temperature = sum(values) / len(values)
    max_temperature = max(values)
    min_temperature = min(values)

    sensor_data = {"temperature": [], "timestamps":[]}
    for row in data:
        timestamp = row["timestamp"]
        if timestamp:
            formatted_time = time.strftime('%H:%M', time.localtime(timestamp - 3 * 3600))
            sensor_data["timestamps"].append(formatted_time)
        sensor_data["temperature"].append(row["temperature"])

    # Retornar a imagem e dados para o frontend
    return render_template('temp.html',
                           sensor_data = sensor_data,
                           last_temperature=last_temperature,
                           average_temperature=average_temperature,
                           max_temperature=max_temperature,
                           min_temperature=min_temperature,)

@clima_bp.route('/about')
def about():
    return render_template('about.html')
