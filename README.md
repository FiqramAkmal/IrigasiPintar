# WeatherAI Flask Dashboard

Dashboard WeatherAI berbasis Flask dengan:
- login JWT
- autentikasi user dari MariaDB/MySQL
- register akun biasa
- role-based access `admin` dan `user`
- kontrol perangkat mode `auto/manual`
- monitoring realtime sensor via MQTT
- live camera MJPEG + panel plant disease dari Raspberry Pi
- penyimpanan log sensor, prediksi, dan deteksi penyakit
- export log ke CSV dari dashboard
- integrasi Open-Meteo untuk forecast cuaca

## Fitur Utama
- Login page dengan JWT cookie
- Register akun baru dengan role default `user`
- Dashboard forecast + telemetry sensor realtime
- Monitoring realtime temperatur, humidity, dan soil moisture
- Status sensor `Live/Offline` berdasarkan data MQTT terakhir
- Live camera MJPEG dan snapshot disease detection
- Telemetry disease via MQTT topic terpisah
- Kontrol mode `auto/manual` khusus admin
- Penyimpanan histori ke database
- Export CSV untuk log sensor, prediksi, dan disease detection
- Cleanup log otomatis mingguan
- Password user di-hash dengan `bcrypt`
- Query database dipusatkan di `db.py`

## Struktur File
- `main.py` — aplikasi Flask utama
- `mqtt_handler.py` — listener dan publisher MQTT
- `db.py` — wrapper koneksi dan query database
- `seed_admin.py` — seed user admin awal
- `simulasi.py` — simulator publish data sensor ke MQTT
- `schema.sql` — struktur tabel database
- `setup.sh` — setup environment lokal otomatis
- `templates/` — HTML templates
- `static/` — CSS, JS, image

## Requirements
- Python 3.10+
- MariaDB/MySQL
- `mariadb` CLI tersedia di shell
- Linux/WSL untuk menjalankan `setup.sh`

## Konfigurasi `.env`
Buat file `.env` di root project.

Contoh lengkap:

```env
JWT_SECRET=ganti-dengan-secret-yang-kuat
JWT_COOKIE_NAME=weatherai_token
JWT_ALGORITHM=HS256
JWT_EXPIRES_SECONDS=28800

ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=weatherai
DB_USER=weatherai_app
DB_PASSWORD=GantiPasswordYangKuat123!

MQTT_BROKER=broker.example.com
MQTT_PORT=8883
MQTT_USERNAME=username_mqtt
MQTT_PASSWORD=password_mqtt
MQTT_TOPIC=WTH/data
MQTT_DISEASE_TOPIC=WTH/disease
MQTT_COMMAND_TOPIC=SIC7/command
MQTT_LIVE_THRESHOLD_SECONDS=15

WEATHER_API_URL=https://api.open-meteo.com/v1/forecast
WEATHER_LATITUDE=-6.925220804796202
WEATHER_LONGITUDE=107.7742369649253

PI_MJPEG_URL=http://<IP_RASPBERRY_PI>:5001/video_feed
PI_DETECTION_IMAGE_URL=http://<IP_RASPBERRY_PI>:5001/latest_detection.jpg
PI_STREAM_LABEL=Live Camera Monitor
PI_DETECTION_LABEL=Plant Disease Detection
PI_SNAPSHOT_REFRESH_MS=5000

MODEL_FILENAME=WeatherAIv2.joblib

FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=true
UI_REFRESH_INTERVAL_MS=5000
```

## Penjelasan Variabel `.env`
### Auth
- `JWT_SECRET` — secret signing JWT
- `JWT_COOKIE_NAME` — nama cookie session JWT
- `JWT_ALGORITHM` — algoritma JWT, default `HS256`
- `JWT_EXPIRES_SECONDS` — masa berlaku token dalam detik

### Admin Seed
- `ADMIN_USERNAME` — username admin awal
- `ADMIN_PASSWORD` — password admin awal untuk `seed_admin.py`

### Database
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

### MQTT
- `MQTT_BROKER` — host broker MQTT
- `MQTT_PORT` — port broker MQTT
- `MQTT_USERNAME` — username broker
- `MQTT_PASSWORD` — password broker
- `MQTT_TOPIC` — topic data sensor yang dibaca dashboard
- `MQTT_DISEASE_TOPIC` — topic telemetry hasil deteksi penyakit
- `MQTT_COMMAND_TOPIC` — topic command kontrol yang dikirim ke perangkat
- `MQTT_LIVE_THRESHOLD_SECONDS` — batas detik untuk status `Live/Offline`

### Weather API
- `WEATHER_API_URL` — endpoint Open-Meteo
- `WEATHER_LATITUDE` — latitude lokasi monitoring
- `WEATHER_LONGITUDE` — longitude lokasi monitoring

### Raspberry Pi Vision
- `PI_MJPEG_URL` — endpoint MJPEG stream (`/video_feed`)
- `PI_DETECTION_IMAGE_URL` — endpoint snapshot deteksi (`/latest_detection.jpg`)
- `PI_STREAM_LABEL` — label panel live monitor
- `PI_DETECTION_LABEL` — label panel plant disease
- `PI_SNAPSHOT_REFRESH_MS` — interval refresh snapshot deteksi dalam milidetik

### App Runtime
- `MODEL_FILENAME` — nama file model `.joblib`
- `FLASK_HOST` — host bind Flask
- `FLASK_PORT` — port Flask
- `FLASK_DEBUG` — mode debug Flask (`true`/`false`)
- `UI_REFRESH_INTERVAL_MS` — interval refresh dashboard dalam milidetik

## Setup Database Manual
Kalau database belum ada, buat dulu:

```sql
CREATE DATABASE weatherai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

## Cara Membuat User MySQL/MariaDB yang Aman
Login dulu sebagai admin database:

```bash
mariadb -u root -p
```

Lalu buat database jika belum ada:

```sql
CREATE DATABASE weatherai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Buat user aplikasi terbatas. Jangan pakai user `root` untuk aplikasi:

```sql
CREATE USER 'weatherai_app'@'localhost'
IDENTIFIED BY 'GantiPasswordYangKuat123!';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
ON weatherai.*
TO 'weatherai_app'@'localhost';

FLUSH PRIVILEGES;
```

Kalau aplikasi Flask berjalan dari mesin lain, ganti host user sesuai asal koneksi, misalnya:

```sql
CREATE USER 'weatherai_app'@'192.168.1.%'
IDENTIFIED BY 'GantiPasswordYangKuat123!';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
ON weatherai.*
TO 'weatherai_app'@'192.168.1.%';

FLUSH PRIVILEGES;
```

Setelah itu sesuaikan `.env`:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=weatherai
DB_USER=weatherai_app
DB_PASSWORD=GantiPasswordYangKuat123!
```

> Untuk runtime production, lebih aman pisahkan user migrasi dan user aplikasi.

## Struktur Schema Database
`schema.sql` sekarang membuat tabel berikut:
- `users`
- `sensor_readings`
- `prediction_logs`
- `disease_detections`
- `auth_logs`

## Setup Otomatis
Jalankan:

```bash
bash setup.sh
```

Script ini akan:
- load `.env`
- validasi env penting
- buat virtualenv `.venv`
- install dependency Python dari `requirements.txt`
- cek koneksi database
- apply `schema.sql`
- seed admin awal
- compile-check file Python

## Urutan Setup yang Disarankan
1. Buat database `weatherai`.
2. Buat user aplikasi MariaDB/MySQL terbatas, jangan `root`.
3. Isi file `.env` sesuai host, user, password, MQTT, JWT, dan endpoint Raspberry Pi.
4. Jalankan `bash setup.sh`.
5. Aktifkan virtualenv lalu jalankan `python main.py`.

Contoh alur singkat:

```bash
bash setup.sh
source .venv/bin/activate
python main.py
```

## Menjalankan Aplikasi
Aktifkan virtualenv:

```bash
source .venv/bin/activate
```

Jalankan Flask app:

```bash
python main.py
```

Buka dashboard:
- `http://127.0.0.1:5000`

## Login dan Register
- Login memakai akun dari tabel `users`
- Admin awal dibuat oleh `seed_admin.py`
- Register tersedia di `/register`
- Akun hasil register otomatis diberi role `user`

## Role dan Privilege
### `admin`
- bisa monitoring dashboard
- bisa kontrol perangkat
- bisa ubah mode `auto/manual`
- bisa kirim manual command `on/off`
- bisa export CSV log dari dashboard

### `user`
- hanya bisa monitoring
- tidak bisa post command kontrol
- tidak bisa export CSV log
- endpoint `POST /api/control` akan ditolak dengan `403`

## Mode Kontrol
### Auto
- keputusan kontrol mengikuti hasil program
- manual command tidak bisa dipakai

### Manual
- hanya admin yang bisa mengaktifkan
- admin bisa mengirim `Pump ON` atau `Pump OFF`

## Endpoint Penting
- `GET /` — dashboard
- `GET /login` — halaman login
- `GET /register` — halaman register
- `GET /api/status` — data dashboard realtime
- `POST /api/control` — kontrol mode/command, khusus admin
- `GET /export/sensor-logs.csv` — export log sensor, khusus admin
- `GET /export/prediction-logs.csv` — export log prediksi, khusus admin
- `GET /export/disease-logs.csv` — export log disease detection, khusus admin

## Logging dan Retensi
Sistem sekarang menyimpan:
- log pembacaan sensor ke `sensor_readings`
- log prediksi model ke `prediction_logs`
- log hasil deteksi penyakit ke `disease_detections`
- log auth ke `auth_logs`

Retensi log saat ini:
- log yang lebih tua dari `7 hari` dihapus otomatis
- cleanup dicek saat aplikasi berjalan
- `sensor_readings` dibersihkan berdasarkan `received_at`
- tabel lain dibersihkan berdasarkan `created_at`

## Simulasi MQTT
Untuk mensimulasikan data sensor ke broker MQTT:

```bash
python simulasi.py
```

Contoh opsi lain:

```bash
python simulasi.py --interval 1
python simulasi.py --count 20
python simulasi.py --profile dry
python simulasi.py --profile wet
```

Payload yang dikirim simulator sesuai format yang dibutuhkan app:

```json
{
  "temperature": "27.45",
  "humidity": "66.20",
  "soil": "52"
}
```

## Seed Admin Ulang
Kalau perlu membuat ulang admin:

```bash
python seed_admin.py
```

Kalau user sudah ada, script tidak akan overwrite otomatis.

## Catatan Security
- Password user disimpan dengan `bcrypt`
- Query SQL dipusatkan di `db.py` dan parameterized
- JWT disimpan di cookie `HttpOnly`
- Endpoint kontrol dan export CSV memakai guard admin di backend
- Jangan commit `.env` ke repository
- Untuk production, aktifkan HTTPS dan set cookie `secure`

## Catatan Arsitektur Saat Ini
- Login user berasal dari tabel `users`
- Auth event masuk ke `auth_logs`
- Data sensor realtime masih dibaca dari memory MQTT listener, lalu disimpan ke DB saat request dashboard/API
- State kontrol `auto/manual` masih in-memory, belum persisten ke database
- Status `Live/Offline` bergantung pada waktu pesan MQTT terakhir yang diterima
- Vision panel menampilkan MJPEG/snapshot dari Raspberry Pi dan telemetry disease dari MQTT topic terpisah

## Next Improvement yang Disarankan
- Simpan state kontrol ke database
- Simpan histori sensor langsung dari `mqtt_handler.py`
- Re-check status user aktif dari DB pada setiap request JWT
- Tambah rate limiting login
- Tambah CSRF protection
- Tambah session/token revocation di database
- Tambah admin panel manajemen user
