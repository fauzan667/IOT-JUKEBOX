# Flowchart & State Machine: ESP32 Minecraft Jukebox (LittleFS Flash)

Dokumen ini menjelaskan alur logika kerja (Flowchart) dan diagram status (State Machine) dari sistem **ESP32 Minecraft Jukebox** menggunakan **Internal Flash (LittleFS)** tanpa MicroSD Card.

---

## 1. Flowchart Sistem (Mermaid Diagram)

```mermaid
flowchart TD
    Start([Power On / Reset ESP32]) --> InitHardware[Inisialisasi Hardware:\n- Serial 115200\n- Sensor TCS3000/TCS3200 (S0-S3, OUT)\n- Mount LittleFS Flash Internal]
    
    InitHardware --> CheckFS{LittleFS Flash\nBerhasil Mount?}
    CheckFS -- Tidak --> FSError[LED Merah / Log Error Serial:\nFormat partisi Flash LittleFS] --> Halt([Sistem Halt])
    CheckFS -- Ya --> InitBT[Inisialisasi Bluetooth A2DP Source:\nHubungkan ke YMX-868BT]

    InitBT --> CheckBT{Terkoneksi ke\nBT Speaker?}
    CheckBT -- Tidak --> WaitBT[Tunggu & Coba Reconnect...] --> CheckBT
    CheckBT -- Ya --> Standby[Status: STANDBY / IDLE\nSensor Warna Membaca Ambien Gelap Dalam Box]

    Standby --> ReadSensor[Baca Data Sensor Warna\nNilai RGB + Clear Channel]
    
    ReadSensor --> DiscDetected{Ada Disc Masuk?\nClear Channel > Threshold}
    DiscDetected -- Tidak --> Standby
    DiscDetected -- Ya --> DebounceIn[Tunggu Stabilisasi Fisik Disc\nDebounce ~350ms]
    
    DebounceIn --> ClassifyColor[Hitung Normalisasi RGB\nUkur Euclidean Distance ke Database Disc]
    
    ClassifyColor --> MatchDisc{Warna Cocok\ndengan Disc?}
    MatchDisc -- Tidak --> UnknownDisc[Warna Tidak Dikenali\nPutar Track Fallback] --> WaitForRemoval[Tunggu Kaset Dikeluarkan]
    
    MatchDisc -- Ya --> PlayAudio[Buka File Lagu di LittleFS Flash:\nContoh: LittleFS.open('/13.mp3')\nStream Audio via A2DP ke BT Speaker]
    
    PlayAudio --> LoopPlaying{Apakah Disc\nMasih Ada?}
    LoopPlaying -- Ya --> CheckEOF{Lagu Selesai?\nEnd Of File}
    CheckEOF -- Tidak --> StreamChunk[Stream Buffer PCM ke A2DP] --> LoopPlaying
    CheckEOF -- Ya --> Standby
    
    LoopPlaying -- Tidak / Dicabut --> StopAudio[Hentikan Stream Audio Segera\nClose File Handle LittleFS]
    StopAudio --> DebounceOut[Tunggu Debounce Cabut ~250ms] --> Standby
    
    WaitForRemoval --> CheckRemoved{Disc Sudah\nDicabut?}
    CheckRemoved -- Tidak --> WaitForRemoval
    CheckRemoved -- Ya --> Standby
```

---

## 2. Text / ASCII Flowchart

```text
+--------------------------------------------------------------+
|                    POWER ON / RESTART                        |
+--------------------------------------------------------------+
                               |
                               v
+--------------------------------------------------------------+
|  1. Inisialisasi: Serial 115200, Sensor TCS3000, LittleFS    |
|  2. Validasi filesystem LittleFS (/moogcity.mp3, dll)        |
|  3. Sambungkan ESP32 Bluetooth A2DP ke Speaker YMX-868BT     |
+--------------------------------------------------------------+
                               |
            [ Bluetooth Terkoneksi? ]
                 /                   \
               TIDAK                  YA
               /                        \
    (Coba reconnect berkala)             v
                         +-----------------------------------+
                         |           STATE: IDLE             |
                         |  - Sensor membaca ambient dalam   |
                         |  - Menunggu disc dimasukkan       |
                         +-----------------------------------+
                                         |
                       [ Apakah ada disc terdeteksi? ]
                       [ (Clear Channel > Threshold)  ]
                                         |
                                         v
                         +-----------------------------------+
                         |         STATE: DEBOUNCE           |
                         |  Tunggu 350ms agar disc duduk pas |
                         |  di slot dasar sensor             |
                         +-----------------------------------+
                                         |
                                         v
                         +-----------------------------------+
                         |     STATE: COLOR RECOGNITION      |
                         |  - Baca Red, Green, Blue, Clear   |
                         |  - Hitung normalized RGB          |
                         |  - Cari jarak warna terdekat      |
                         +-----------------------------------+
                                         |
                       [ Apakah warna cocok dengan database? ]
                              /                     \
                            TIDAK                   YA
                            /                         \
            +-----------------------+     +--------------------------+
            |  Disc tidak dikenali  |     | STATE: PLAYING           |
            |  Tetap diam           |     | - Buka file di LittleFS  |
            |  Tunggu disc dilepas  |     | - Stream PCM ke A2DP     |
            +-----------------------+     +--------------------------+
                                                       |
                                            [ Disc masih di slot? ]
                                                   /        \
                                                 YA        TIDAK
                                                /            \
                                 (Lanjut stream)              v
                                                  +-----------------------+
                                                  | STATE: STOPPING       |
                                                  | - Matikan audio       |
                                                  | - Flush A2DP stream   |
                                                  | - Reset ke IDLE       |
                                                  +-----------------------+
```
