# CATATAN Progres WeatherAI

## Status Saat Ini
Project sudah direfactor dari Streamlit ke Flask dan sekarang sudah memiliki fondasi berikut:
- dashboard Flask dengan `templates/` dan `static/`
- login berbasis JWT
- autentikasi user dari database MariaDB/MySQL
- register akun baru dengan role `user`
- role-based access: `admin` bisa kontrol dan export, `user` hanya monitoring
- kontrol perangkat mode `auto/manual`
- indikator status sensor `Live/Offline`
- monitoring realtime visual untuk temperatur, humidity, dan soil moisture
- live monitor MJPEG dan snapshot deteksi penyakit dari Raspberry Pi
- wrapper query database terpusat di `db.py`
- password di-hash menggunakan `bcrypt`
- setup script `setup.sh`
- schema database di `schema.sql`
- dokumentasi setup di `README.md`
- simulator MQTT untuk testing sensor di `simulasi.py`

## Yang Sudah Dikerjakan

### 1. Refactor UI ke Flask
- `main.py` tidak lagi memakai Streamlit.
- Dashboard sekarang dirender dengan Flask.
- Template utama ada di `templates/index.html`.
- Asset dipindah ke:
  - `static/css/style.css`
  - `static/js/dashboard.js`
  - `static/images/bg.jpeg`

### 2. Dashboard Live Update
- Halaman melakukan refresh parsial via endpoint `/api/status`.
- Chart dan tabel di-update tanpa reload penuh.
- Performa chart sudah dirapikan agar tidak membesar terus dan tidak berat.

### 3. Monitoring Realtime Visual
- Dashboard sekarang punya section visual untuk:
  - temperatur
  - humidity
  - soil moisture
- Sudah ada ilustrasi gauge, water level, dan soil bar.
- Data sensor realtime tetap dipakai di ilustrasi sensor.
- Ringkasan paling atas sekarang memakai forecast API:
  - `Temperature Forecast`
  - `Precipitation Forecast`

### 4. Status Live/Offline Sensor
- Badge `Live` muncul jika aplikasi menerima data MQTT dari ESP/simulator dalam batas waktu tertentu.
- Badge `Offline` muncul jika data terakhir terlalu lama atau belum pernah diterima.
- Status ini dihitung dari timestamp pesan MQTT terakhir yang diterima listener.

### 5. Login JWT
- Login tersedia di `templates/login.html`.
- JWT dibuat di backend dan disimpan di cookie `HttpOnly`.
- Route yang diproteksi akan redirect ke login atau return `401` untuk endpoint API.

### 6. Database Integration
- Koneksi DB ada di `db.py`.
- Query sudah dipusatkan lewat wrapper database.
- Semua query saat ini parameterized.
- Default role database untuk user baru tetap `user`, bukan `admin`.
- Tabel utama sekarang:
  - `users`
  - `sensor_readings`
  - `prediction_logs`
  - `disease_detections`
  - `auth_logs`

### 7. Logging Database
- Log pembacaan sensor masuk ke `sensor_readings`.
- Log prediksi model masuk ke `prediction_logs`.
- Log hasil deteksi penyakit masuk ke `disease_detections`.
- Log login/logout tetap masuk ke `auth_logs`.
- Cleanup mingguan sudah disinkronkan: `sensor_readings` pakai `received_at`, tabel lain pakai `created_at`.

### 8. Cleanup Mingguan
- Sudah ada cleanup otomatis untuk log lama.
- Data yang lebih tua dari `7 hari` dihapus otomatis.
- Retensi saat ini dicek saat aplikasi berjalan.

### 9. Export CSV
- Di bagian paling bawah dashboard sudah ada panel `Export Logs`.
- Admin bisa export:
  - sensor logs
  - prediction logs
  - disease logs
- User biasa tidak bisa mengunduh log.

### 10. Admin Seed
- File `seed_admin.py` dipakai untuk membuat admin awal.
- Username dan password admin diambil dari `.env`.
- Password disimpan dalam bentuk hash `bcrypt`.

### 11. Register dan Role
- Halaman register ada di `templates/register.html`.
- User baru otomatis punya role `user`.
- Role `user` hanya boleh monitoring.
- Role `admin` boleh monitoring + kontrol MQTT + export log.

### 12. Kontrol Auto/Manual
- Sudah ada panel `Control Center` di dashboard.
- Admin bisa memilih mode:
  - `auto`
  - `manual`
- Saat `auto` aktif:
  - command mengikuti hasil program
  - tombol manual tidak bisa dipakai
- Saat `manual` aktif:
  - admin bisa kirim `ON/OFF`
- User biasa tidak bisa memakai endpoint kontrol.
- Backend sudah enforce admin-only pada `POST /api/control`.

### 13. MQTT
- `mqtt_handler.py` sekarang membaca konfigurasi dari `.env`.
- Kredensial broker tidak lagi hardcoded.
- Topic sensor data, disease telemetry, dan command sekarang configurable lewat environment.

### 14. Vision Monitor Raspberry Pi
- Sudah ada panel `Vision Monitor` di antara telemetry dan grafik.
- Panel kiri menampilkan MJPEG live monitor.
- Panel kanan menampilkan snapshot deteksi penyakit.
- Telemetry disease dari MQTT juga ditampilkan:
  - kondisi daun
  - tingkat keyakinan
  - status deteksi
  - waktu deteksi

### 15. Simulator MQTT
- `simulasi.py` dibuat untuk mensimulasikan data sensor ke broker MQTT.
- Payload simulator sudah sesuai format yang dibutuhkan dashboard:
  - `temperature`
  - `humidity`
  - `soil`
- Tersedia profile simulasi:
  - `normal`
  - `dry`
  - `wet`

### 16. Setup dan Dokumentasi
- `setup.sh` untuk setup environment lokal.
- `schema.sql` untuk membuat struktur tabel terbaru.
- `README.md` sudah dirapikan dan disinkronkan dengan kondisi terbaru.

## Konfigurasi via `.env`
Konfigurasi penting sekarang dipindahkan ke `.env`, antara lain:
- JWT config
- DB config
- MQTT broker/topic config
- weather API config
- Raspberry Pi MJPEG / detection snapshot config
- host/port Flask
- refresh interval UI
- threshold `Live/Offline`
- nama file model `.joblib`

## File Penting
- `main.py`
- `mqtt_handler.py`
- `db.py`
- `seed_admin.py`
- `simulasi.py`
- `schema.sql`
- `setup.sh`
- `README.md`
- `CATATAN.md`
- `templates/index.html`
- `templates/login.html`
- `templates/register.html`
- `static/css/style.css`
- `static/js/dashboard.js`

## Catatan Arsitektur Sekarang
- Data sensor realtime masih dibaca dari memory MQTT listener.
- Histori sensor dan disease saat ini disimpan ketika request dashboard/API dipanggil.
- JWT belum disimpan ke database.
- Logout saat ini menghapus cookie, belum revoke token di sisi server.
- State kontrol `auto/manual` masih disimpan di memory server.
- Kalau server restart, mode kontrol akan kembali ke default.
- Status `Live/Offline` bergantung pada waktu pesan MQTT terakhir yang diterima.
- Vision panel mengambil stream/snapshot dari Raspberry Pi dan telemetry disease dari MQTT.

## Hal yang Masih Bisa Ditingkatkan

### Prioritas Teknis
- pindahkan penyimpanan `sensor_readings` dan `disease_detections` langsung ke `mqtt_handler.py`
- simpan state kontrol ke database
- re-check user aktif dari DB pada setiap request JWT
- tambahkan halaman admin untuk manajemen user
- tambahkan rate limiting login
- tambahkan CSRF protection
- tambahkan revoke session/token di DB

### Prioritas Fitur
- halaman histori sensor
- halaman histori penyiraman
- admin panel promote/demote role user
- toggle `is_active` user
- filter data histori berdasarkan waktu
- indikator detail kualitas koneksi sensor

## Cara Lanjut Nanti
Kalau mau melanjutkan pengembangan, titik paling masuk akal berikutnya:
1. persist state kontrol ke database
2. bikin admin panel manajemen user
3. pindahkan insert histori sensor dan disease ke layer MQTT listener
4. tambah histori monitoring berbasis database
5. tambah kontrol akses yang lebih ketat per endpoint
6. tambahkan `.env.example` dan `.gitignore`

## Catatan Operasional
- Pastikan `.env` terisi lengkap sebelum menjalankan app.
- Jalankan `bash setup.sh` untuk setup awal.
- Jalankan ulang `schema.sql` ke database setelah update schema.
- Jalankan `python seed_admin.py` jika perlu membuat admin ulang.
- Jalankan app dengan `python main.py`.
- Jalankan `python simulasi.py` untuk mensimulasikan data sensor ke MQTT.
