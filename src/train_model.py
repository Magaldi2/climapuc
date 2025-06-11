# train_model.py (versão corrigida)

import pandas as pd
import mysql.connector
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
from dotenv import load_dotenv

load_dotenv()

def train_and_save_model():
    print("Iniciando o processo de treinamento do modelo de previsão de chuva...")

    try:
        print("Conectando ao banco de dados MySQL...")
        connection = mysql.connector.connect(
            host="mysql",
            user="root",
            password="example",
            database="weather_data"
        )

        # A query agora ordena por timestamp para garantir a ordem cronológica
        query = "SELECT timestamp, temperature, humidity, average_wind_speed, rain_level FROM sensor_data WHERE temperature IS NOT NULL AND humidity IS NOT NULL AND average_wind_speed IS NOT NULL AND rain_level IS NOT NULL ORDER BY timestamp ASC"
        df = pd.read_sql(query, connection)
        print(f"Dados extraídos com sucesso. Total de registros: {len(df)}")

    except mysql.connector.Error as e:
        print(f"Erro ao conectar ou extrair dados do MySQL: {e}")
        return
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

    if len(df) < 100:
        print("Dados insuficientes para treinar o modelo. Cancele o treinamento.")
        return

    # --- 2. Preparação dos Dados (Com a Lógica Corrigida) ---
    print("Preparando os dados...")


    # Calculamos a diferença no nível de chuva entre a linha atual e a anterior
    rain_increase = df['rain_level'].diff()

    # Criamos a variável alvo: 'ocorreu_chuva' é 1 se o nível de chuva AUMENTOU.
    df['ocorreu_chuva'] = (rain_increase > 0.0001).astype(int) # Usamos um pequeno limiar para ignorar ruído

    # O primeiro valor de .diff() é sempre NaN (nulo), então preenchemos com 0 (não choveu)
    df.fillna(0, inplace=True)

    features = ['temperature', 'humidity', 'average_wind_speed']
    X = df[features]
    y = df['ocorreu_chuva']

    print("Distribuição da variável alvo (ocorreu_chuva) CORRIGIDA:")
    print(y.value_counts())

    # --- 3. Treinamento do Modelo ---
    print("Dividindo dados em conjuntos de treino e teste...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("Treinando o modelo RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)

    # --- 4. Avaliação do Modelo ---
    print("Avaliando o modelo...")
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Acurácia do modelo no conjunto de teste: {accuracy * 100:.2f}%")

    # Imprime um relatório mais detalhado
    print("\nRelatório de Classificação:")
    print(classification_report(y_test, y_pred))

    # --- 5. Salvando o Modelo Treinado ---
    print("Salvando o modelo treinado em 'rain_model.joblib'...")
    joblib.dump(model, 'rain_model.joblib')
    print("Modelo salvo com sucesso!")

    joblib.dump(features, 'model_features.joblib')
    print("Lista de features do modelo salva em 'model_features.joblib'.")
    print("\nProcesso de treinamento concluído!")

if __name__ == '__main__':
    train_and_save_model()
