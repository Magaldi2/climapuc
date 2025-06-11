-- Criação do banco de dados se ele não existir
CREATE DATABASE IF NOT EXISTS weather_data;
USE weather_data;

-- Tabela para armazenar os dados dos sensores
CREATE TABLE IF NOT EXISTS sensor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rain_level FLOAT NULL,
    average_wind_speed FLOAT NULL,
    wind_direction FLOAT NULL,
    humidity FLOAT NULL,
    uv_index FLOAT NULL,
    solar_radiation FLOAT NULL,
    temperature FLOAT NULL,
    timestamp BIGINT NOT NULL, -- Armazena o tempo em formato UNIX UTC (padrão)
    UNIQUE KEY unique_timestamp (timestamp)
);
-- Tabela para armazenar os dados fixos e de identificação de cada luminária.
CREATE TABLE luminaires (
    id INT PRIMARY KEY AUTO_INCREMENT,
    external_id INT UNIQUE NOT NULL,                       -- O 'id' original do JSON (ex: 7)
    name VARCHAR(255),                                     -- O 'nome' da luminária (ex: "Luminária 02")
    serial_number VARCHAR(100),                            -- O campo 'serial'
    location_description VARCHAR(255),                     -- O campo 'trecho'
    
    latitude DECIMAL(10, 8) NOT NULL,                      -- 'latitude'
    longitude DECIMAL(11, 8) NOT NULL,                     -- 'longitude'
    
    status VARCHAR(50),                                    -- O 'status' geral (ex: "OK")
    is_active BOOLEAN DEFAULT true,                        -- O campo 'active'
    
    modem_deveui VARCHAR(16) UNIQUE,                       -- O 'devEui' do modem
    
    -- Alterado de TIMESTAMPTZ para TIMESTAMP
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Adicionado ON UPDATE para atualização automática
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabela para armazenar as leituras periódicas (time-series data) de cada luminária.
CREATE TABLE luminaire_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    luminaire_id INT NOT NULL,                             -- Chave estrangeira para a tabela 'luminaires'
    
    -- Alterado de TIMESTAMPTZ para TIMESTAMP
    recorded_at TIMESTAMP NOT NULL,                        -- O timestamp da leitura ('lastCommunication')
    
    ldr_value INT,                                         -- 'ldr'
    dimmer_level INT,                                      -- 'dimmer'
    lamp_status VARCHAR(20),                               -- 'statusLampada' (ex: "ACESA")
    relay_state VARCHAR(20),                               -- 'estadoRele' (ex: "ATIVADO")
    is_online BOOLEAN,                                     -- 'online'
    burning_hours BIGINT,                                  -- 'burningHours'
    
    -- Dados da Conexão
    signal_quality VARCHAR(20),                            -- 'signalQuality' (ex: "BOM")
    data_rate VARCHAR(20),                                 -- 'dataRate'
    
    -- Chave estrangeira que garante a integridade referencial
    FOREIGN KEY (luminaire_id) REFERENCES luminaires(id) ON DELETE CASCADE
);

-- Criar um índice no timestamp da leitura para otimizar consultas por período.
CREATE INDEX idx_luminaire_data_recorded_at ON luminaire_data (recorded_at DESC);