---
name: minecraft-jukebox-esp32
description: >-
  Panduan teknis dan operasional untuk perakitan, kalibrasi warna, konfigurasi audio,
  dan firmware ESP32 Minecraft Jukebox dengan sensor warna TCS3000/TCS3200 (S0-S3, OUT, VCC, GND, LED),
  penyimpanan internal LittleFS Flash (tanpa SD Card), dan streaming audio Bluetooth A2DP Source ke Bluetooth Speaker.
---

# Minecraft Jukebox ESP32 Engineering Skill (TCS3000 & LittleFS)

Skill ini memuat instruksi lengkap, batasan hardware, prosedur kalibrasi warna disc, serta konfigurasi streaming audio untuk proyek **Minecraft Jukebox ESP32** dengan sensor warna **TCS3000 / TCS3200** (8 pin) dan penyimpanan internal **LittleFS Flash**.

---

## 1. Arsitektur Inti & Penyimpanan Internal LittleFS

> [!CRITICAL]
> **Hanya gunakan ESP32 Classic (ESP32-WROOM-32 / ESP32-WROVER)!**
> Varian baru seperti **ESP32-S2, ESP32-S3, dan ESP32-C3 TIDAK MENDUKUNG Bluetooth Classic (BR/EDR)**. Hanya ESP32 Classic yang mendukung streaming audio A2DP Source ke Bluetooth Speaker standar.

### Alokasi Partisi Flash (4MB Flash):
- **App Firmware (`app0`)**: 1.31 MB (`0x140000`)
- **LittleFS Filesystem (`spiffs`)**: 2.81 MB (`0x2B0000`) khusus file audio MP3.
- Konfigurasi tabel partisi tersimpan di `partitions_custom.csv`.

---

## 2. Pemetaan Pinout Hardware Sensor TCS3000 / TCS3200

Sensor warna **TCS3000 / TCS3200** memiliki 8 pin dan dihubungkan langsung ke ESP32 sebagai berikut:

| Pin Sensor | Pin ESP32 | Mode Pin ESP32 | Keterangan |
| :--- | :--- | :--- | :--- |
| **VCC** | **3.3V** | Power | Hubungkan ke 3.3V agar level tegangan pin OUT aman untuk ESP32 |
| **GND** | **GND** | Ground | Ground bersama |
| **S0** | **GPIO 14** | OUTPUT | Skala Frekuensi (HIGH) |
| **S1** | **GPIO 27** | OUTPUT | Skala Frekuensi (LOW -> Set ke 20% scaling) |
| **S2** | **GPIO 26** | OUTPUT | Seleksi Filter Fotodioda |
| **S3** | **GPIO 25** | OUTPUT | Seleksi Filter Fotodioda |
| **OUT** | **GPIO 33** | INPUT | Sinyal pulsa frekuensi warna (dibaca dengan `pulseIn`) |
| **LED** | **GPIO 32** | OUTPUT | Menyalakan 4 buah LED putih sensor (HIGH = ON, LOW = OFF) |

---

## 3. Logika Pembacaan Warna & Deteksi Disc

Sensor TCS3000 mengubah intensitas cahaya menjadi frekuensi gelombang kotak:
- Durasi pulsa (`pulseIn(OUT, LOW)`) berbanding terbalik dengan intensitas cahaya:
  \[
  \text{Intensitas} = \frac{1}{\text{Pulse Duration}}
  \]
- **Normalisasi Warna:**
  \[
  r = \frac{I_R}{I_R + I_G + I_B}, \quad g = \frac{I_G}{I_R + I_G + I_B}, \quad b = \frac{I_B}{I_R + I_G + I_B}
  \]
- **Deteksi Disc Masuk:**
  Ketika disc masuk, pantulan cahaya putih dari LED ke fotodioda Clear menghasilkan durasi pulsa yang sangat singkat (`pulseClear < 95 us`). Jika slot kosong/gelap, durasi pulsa Clear sangat panjang atau timeout.

---

## 4. Tabel Referensi Disc Resmi Minecraft
| Nama Disc | Warna Piringan / Label | Path LittleFS | Nilai Acuan (R, G, B Normalized) |
| :--- | :--- | :--- | :--- |
| **13** | Kuning Emas (Gold/Yellow) | `/13.mp3` | r: 0.50, g: 0.42, b: 0.08 |
| **cat** | Hijau Terang (Lime Green) | `/cat.mp3` | r: 0.20, g: 0.65, b: 0.15 |
| **blocks** | Merah / Oranye (Red-Orange)| `/blocks.mp3` | r: 0.68, g: 0.22, b: 0.10 |
| **chirp** | Merah Tua / Crimson | `/chirp.mp3` | r: 0.65, g: 0.18, b: 0.17 |
| **far** | Hijau Muda / Pastel | `/far.mp3` | r: 0.35, g: 0.50, b: 0.15 |
| **mall** | Ungu / Violet (Purple) | `/mall.mp3` | r: 0.38, g: 0.22, b: 0.40 |
| **mellohi** | Magenta / Pink Lembut | `/mellohi.mp3` | r: 0.48, g: 0.22, b: 0.30 |
| **stal** | Hitam Pekat | `/stal.mp3` | r: 0.33, g: 0.33, b: 0.34 (Clear Lux sangat rendah) |
| **strad** | Putih Gading / Krem | `/strad.mp3` | r: 0.38, g: 0.38, b: 0.24 (Clear Lux sangat tinggi) |
| **ward** | Hijau Gelap / Pine | `/ward.mp3` | r: 0.18, g: 0.52, b: 0.30 |
| **11** | Pecah / Abu Gelap | `/11.mp3` | r: 0.33, g: 0.33, b: 0.34 (Clear Rendah) |
| **wait** | Biru Laut (Cyan / Blue) | `/wait.mp3` | r: 0.15, g: 0.35, b: 0.50 |
| **otherside** | Biru Muda & Hijau Teal | `/otherside.mp3` | r: 0.12, g: 0.50, b: 0.38 |
| **pigstep** | Merah Netherite / Hitam-Merah | `/pigstep.mp3` | r: 0.58, g: 0.18, b: 0.24 |
| **relic** | Tembaga / Cokelat Oranye | `/relic.mp3` | r: 0.55, g: 0.32, b: 0.13 |

---

## 5. Prosedur Kalibrasi Warna (Step-by-Step)

1. Set `#define CALIBRATION_MODE 1` di [`src/main.cpp`](file:///c:/Users/MSI%20GAMING/Documents/Project/JUKEBOX/src/main.cpp#L23).
2. Upload firmware dan pantau Serial Monitor (115200 baud).
3. Masukkan kaset disc Anda ke dalam slot box.
4. Catat nilai pulsa `Clear` serta normalized `r`, `g`, `b`.
5. Masukkan nilai tersebut ke dalam array `discDatabase[]`.
6. Kembalikan ke `#define CALIBRATION_MODE 0` lalu upload ulang.

---

## 6. Konfigurasi Bluetooth A2DP Source & Target Speaker

- **Target Speaker**: `YMX-868BT`
- **MAC Address**: `12:11:8A:1A:2A:08`
- **Class of Device (COD)**: `0x240418` (Audio / Loudspeaker)
- **PIN Code**: `0000` (Fixed PIN)
- **Metode Koneksi**: Direct MAC auto-reconnect (`a2dp_source.set_auto_reconnect(TARGET_SPEAKER_MAC, 10)`) dengan fallback discovery scan.

