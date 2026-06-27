CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor_readings (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  topic VARCHAR(100) NOT NULL,
  temperature DECIMAL(5,2) NOT NULL,
  humidity DECIMAL(5,2) NOT NULL,
  soil DECIMAL(5,2) NOT NULL,
  payload_json JSON NULL,
  received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_sensor_received_at (received_at),
  INDEX idx_sensor_topic (topic)
);

CREATE TABLE IF NOT EXISTS prediction_logs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  sensor_reading_id BIGINT UNSIGNED NULL,
  forecast_temperature DECIMAL(5,2) NOT NULL,
  forecast_precipitation_probability DECIMAL(5,2) NOT NULL,
  prediction VARCHAR(50) NOT NULL,
  status_message VARCHAR(255) NOT NULL,
  mqtt_command VARCHAR(20) NOT NULL,
  soil DECIMAL(5,2) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_prediction_created_at (created_at),
  CONSTRAINT fk_prediction_sensor
    FOREIGN KEY (sensor_reading_id) REFERENCES sensor_readings(id)
    ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS disease_detections (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  topic VARCHAR(100) NOT NULL,
  kondisi_daun VARCHAR(100) NOT NULL,
  tingkat_keyakinan DECIMAL(6,2) NOT NULL,
  status_deteksi VARCHAR(50) NOT NULL,
  camera_status VARCHAR(30) NOT NULL,
  stream_status VARCHAR(30) NOT NULL,
  model_status VARCHAR(30) NOT NULL,
  detected_at VARCHAR(50) NOT NULL,
  payload_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_disease_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS auth_logs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL,
  event_type VARCHAR(30) NOT NULL,
  ip_address VARCHAR(64) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_auth_created_at (created_at)
);
