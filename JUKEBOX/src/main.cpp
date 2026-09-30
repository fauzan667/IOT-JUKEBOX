/**
 * ============================================================================
 * Proyek: ESP32 Minecraft Jukebox
 * Sensor: TCS3000 / TCS3200 (8 Pin: S0, S1, S2, S3, OUT, VCC, GND, LED)
 * Media: LittleFS Internal Flash (Partisi 2.8 MB, Tanpa MicroSD Card)
 * Output: Bluetooth Speaker A2DP Source
 * Target Speaker: YMX-868BT (MAC: 12:11:8A:1A:2A:08)
 * Port: COM3
 * ============================================================================
 */

#include <Arduino.h>
#include <FS.h>
#include <LittleFS.h>
#include <freertos/ringbuf.h>
#include "BluetoothA2DPSource.h"
#include "MP3DecoderHelix.h"

// ============================================================================
// 1. KONFIGURASI TARGET BLUETOOTH SPEAKER (YMX-868BT)
// ============================================================================
const char* BT_SPEAKER_NAME = "YMX-868BT";
esp_bd_addr_t TARGET_SPEAKER_MAC = {0x12, 0x11, 0x8A, 0x1A, 0x2A, 0x08};

// Set ke 1 untuk Serial Monitor Raw Color Dump saat kalibrasi kaset fisik
#define CALIBRATION_MODE 0

// ============================================================================
// 2. PEMETAAN PIN HARDWARE SENSOR TCS3000 / TCS3200
// ============================================================================
#define S0_PIN    14    // Skala Frekuensi
#define S1_PIN    27    // Skala Frekuensi
#define S2_PIN    26    // Filter Fotodioda
#define S3_PIN    25    // Filter Fotodioda
#define OUT_PIN   33    // Sinyal frekuensi keluaran sensor (Pulse input)
#define LED_PIN   32    // Kontrol lampu LED sensor (HIGH = Nyala)

// Ambang batas durasi pulsa Clear (us) untuk deteksi kaset masuk
// Cahaya pantulan disc membuat durasi pulsa < 100 us
const uint32_t DISC_INSERTED_PULSE_THRESHOLD = 100;

// ============================================================================
// 3. DATABASE WARNA KASET DISK MINECRAFT
// ============================================================================
struct DiscColor {
  const char* trackName;
  const char* filePath;
  float normR;
  float normG;
  float normB;
  float tolerance;
};

const DiscColor discDatabase[] = {
  {"13",        "/13.mp3",        0.50f, 0.42f, 0.08f, 0.12f}, // Kuning Emas
  {"cat",       "/cat.mp3",       0.20f, 0.65f, 0.15f, 0.12f}, // Hijau Terang
  {"blocks",    "/blocks.mp3",    0.68f, 0.22f, 0.10f, 0.12f}, // Oranye / Merah
  {"chirp",     "/chirp.mp3",     0.65f, 0.18f, 0.17f, 0.12f}, // Merah Tua
  {"far",       "/far.mp3",       0.35f, 0.50f, 0.15f, 0.12f}, // Hijau Muda
  {"mall",      "/mall.mp3",      0.38f, 0.22f, 0.40f, 0.12f}, // Ungu
  {"mellohi",   "/mellohi.mp3",   0.48f, 0.22f, 0.30f, 0.12f}, // Pink / Magenta
  {"stal",      "/stal.mp3",      0.33f, 0.33f, 0.34f, 0.10f}, // Hitam
  {"strad",     "/strad.mp3",     0.38f, 0.38f, 0.24f, 0.10f}, // Putih
  {"ward",      "/ward.mp3",      0.18f, 0.52f, 0.30f, 0.12f}, // Hijau Gelap
  {"11",        "/11.mp3",        0.33f, 0.33f, 0.34f, 0.10f}, // Abu Gelap
  {"wait",      "/wait.mp3",      0.15f, 0.35f, 0.50f, 0.12f}, // Biru Laut
  {"otherside", "/otherside.mp3", 0.12f, 0.50f, 0.38f, 0.12f}, // Biru Teal
  {"pigstep",   "/pigstep.mp3",   0.58f, 0.18f, 0.24f, 0.12f}, // Merah Netherite
  {"relic",     "/relic.mp3",     0.55f, 0.32f, 0.13f, 0.12f}  // Cokelat Tembaga
};
const size_t NUM_DISCS = sizeof(discDatabase) / sizeof(discDatabase[0]);

// ============================================================================
// 4. OBJEK GLOBAL AUDIO & STATUS
// ============================================================================
BluetoothA2DPSource a2dp_source;
libhelix::MP3DecoderHelix mp3Decoder;
RingbufHandle_t audioRingBuffer = nullptr;
File currentTrackFile;

enum SystemState {
  STATE_WAIT_BLUETOOTH,
  STATE_IDLE_WAIT_DISC,
  STATE_PLAYING
};

SystemState currentState = STATE_WAIT_BLUETOOTH;
int currentPlayingIndex = -1;
unsigned long lastSensorReadTime = 0;
unsigned long lastBtStatusLog = 0;
unsigned long debounceStartTime = 0;
bool isDiscPresent = false;
bool isBtConnected = false;
bool isTrackFileEof = false;
int currentVolume = 80; // 0 - 100%

// Ukuran Ring Buffer Audio (32 KB = 8192 stereo sample = ~185ms audio)
const size_t AUDIO_RINGBUF_SIZE = 32768;
const size_t MP3_READ_CHUNK_SIZE = 512;
uint8_t mp3ReadBuffer[MP3_READ_CHUNK_SIZE];

// ============================================================================
// 5. CALLBACK DEKODER MP3 HELIX
// ============================================================================
void mp3DataCallback(MP3FrameInfo &info, short *pcm_buffer, size_t len, void *ref) {
  if (audioRingBuffer == nullptr || len == 0) return;

  if (info.nChans == 2) {
    // Stereo: langsung masukkan ke ringbuffer
    size_t bytesToSend = len * sizeof(short);
    xRingbufferSend(audioRingBuffer, (void*)pcm_buffer, bytesToSend, pdMS_TO_TICKS(20));
  } else if (info.nChans == 1) {
    // Mono: gandakan sample ke L dan R (Stereo Frame)
    Frame stereoTemp[576];
    size_t samplesRemaining = len;
    size_t offset = 0;

    while (samplesRemaining > 0) {
      size_t batch = min((size_t)576, samplesRemaining);
      for (size_t i = 0; i < batch; i++) {
        stereoTemp[i].channel1 = pcm_buffer[offset + i];
        stereoTemp[i].channel2 = pcm_buffer[offset + i];
      }
      xRingbufferSend(audioRingBuffer, (void*)stereoTemp, batch * sizeof(Frame), pdMS_TO_TICKS(20));
      samplesRemaining -= batch;
      offset += batch;
    }
  }
}

// ============================================================================
// 6. CALLBACK STREAM AUDIO BLUETOOTH A2DP SOURCE
// ============================================================================
int32_t get_sound_data(Frame *data, int32_t frame_count) {
  size_t bytesNeeded = frame_count * sizeof(Frame);

  if (currentState != STATE_PLAYING || audioRingBuffer == nullptr) {
    memset(data, 0, bytesNeeded);
    return frame_count;
  }

  size_t bytesReceived = 0;
  uint8_t *item = (uint8_t*) xRingbufferReceiveUpTo(audioRingBuffer, &bytesReceived, 0, bytesNeeded);

  if (item != nullptr && bytesReceived > 0) {
    memcpy(data, item, bytesReceived);
    vRingbufferReturnItem(audioRingBuffer, (void*)item);
  }

  // Jika data di ring buffer kurang, isi sisanya dengan hening
  if (bytesReceived < bytesNeeded) {
    memset(((uint8_t*)data) + bytesReceived, 0, bytesNeeded - bytesReceived);

    // Jika file MP3 sudah habis dibaca dan ring buffer kosong, selesaikan track
    if (isTrackFileEof && bytesReceived == 0) {
      Serial.println("[AUDIO] Lagu selesai diputar.");
      if (currentTrackFile) {
        currentTrackFile.close();
      }
      currentPlayingIndex = -1;
      currentState = isBtConnected ? STATE_IDLE_WAIT_DISC : STATE_WAIT_BLUETOOTH;
    }
  }

  return frame_count;
}

// ============================================================================
// 7. CALLBACK DISCOVERY & KONEKSI BLUETOOTH
// ============================================================================
bool bt_ssid_callback(const char* ssid, esp_bd_addr_t address, int rssi) {
  char bda_str[18];
  sprintf(bda_str, "%02X:%02X:%02X:%02X:%02X:%02X",
          address[0], address[1], address[2], address[3], address[4], address[5]);
  Serial.printf("[BT SCAN] Ditemukan: \"%s\" [%s] RSSI: %d\n", ssid ? ssid : "(No Name)", bda_str, rssi);

  // Abaikan laptop MSI jika terdeteksi
  if (ssid != nullptr && (strcmp(ssid, "MSI") == 0 || strcasecmp(bda_str, "04:EC:D8:68:15:09") == 0)) {
    return false;
  }

  // Cocokkan MAC target (12:11:8A:1A:2A:08) atau nama "YMX-868BT"
  if (memcmp(address, TARGET_SPEAKER_MAC, 6) == 0 || (ssid && strstr(ssid, "YMX-868BT") != nullptr)) {
    Serial.printf("[BT MATCH] >>> TARGET TERDETEKSI: \"%s\" [%s]! MENGHUBUNGKAN... <<<\n", 
                  (ssid && strlen(ssid) > 0) ? ssid : "YMX-868BT", bda_str);
    return true;
  }

  return false;
}

void bt_connection_state_callback(esp_a2d_connection_state_t state, void *) {
  Serial.printf("[BT STATE] Status Koneksi: %s\n", a2dp_source.to_str(state));
  if (state == ESP_A2D_CONNECTION_STATE_CONNECTED) {
    isBtConnected = true;
    currentState = STATE_IDLE_WAIT_DISC;
    Serial.println("\n**************************************************");
    Serial.println("  [BT SUCCESS] BERHASIL TERHUBUNG KE SPEAKER!    ");
    Serial.println("  Target: YMX-868BT [12:11:8A:1A:2A:08]          ");
    Serial.println("  Jukebox Siap Digunakan. Masukkan Kaset Disc!   ");
    Serial.println("**************************************************\n");
  } else if (state == ESP_A2D_CONNECTION_STATE_DISCONNECTED) {
    isBtConnected = false;
    currentState = STATE_WAIT_BLUETOOTH;
    Serial.println("[BT STATUS] Koneksi terputus. Mencoba rekoneksi otomatis...");
  }
}

// ============================================================================
// 8. PEMBACAAN SENSOR TCS3000 / TCS3200
// ============================================================================
struct ColorReading {
  uint32_t pulseR;
  uint32_t pulseG;
  uint32_t pulseB;
  uint32_t pulseClear;
  float normR;
  float normG;
  float normB;
  bool isDetected;
};

ColorReading readTCS3000() {
  ColorReading c = {0, 0, 0, 0, 0.0f, 0.0f, 0.0f, false};

  // 1. Baca Merah (S2=LOW, S3=LOW)
  digitalWrite(S2_PIN, LOW);
  digitalWrite(S3_PIN, LOW);
  delayMicroseconds(100);
  c.pulseR = pulseIn(OUT_PIN, LOW, 25000);

  // 2. Baca Hijau (S2=HIGH, S3=HIGH)
  digitalWrite(S2_PIN, HIGH);
  digitalWrite(S3_PIN, HIGH);
  delayMicroseconds(100);
  c.pulseG = pulseIn(OUT_PIN, LOW, 25000);

  // 3. Baca Biru (S2=LOW, S3=HIGH)
  digitalWrite(S2_PIN, LOW);
  digitalWrite(S3_PIN, HIGH);
  delayMicroseconds(100);
  c.pulseB = pulseIn(OUT_PIN, LOW, 25000);

  // 4. Baca Clear (S2=HIGH, S3=LOW)
  digitalWrite(S2_PIN, HIGH);
  digitalWrite(S3_PIN, LOW);
  delayMicroseconds(100);
  c.pulseClear = pulseIn(OUT_PIN, LOW, 25000);

  float intR = (c.pulseR > 0) ? (10000.0f / (float)c.pulseR) : 0.0f;
  float intG = (c.pulseG > 0) ? (10000.0f / (float)c.pulseG) : 0.0f;
  float intB = (c.pulseB > 0) ? (10000.0f / (float)c.pulseB) : 0.0f;

  float sum = intR + intG + intB;
  if (sum > 0.001f) {
    c.normR = intR / sum;
    c.normG = intG / sum;
    c.normB = intB / sum;
  }

  // Deteksi kaset jika ada pantulan cahaya (pulseClear < ambang batas dan > 0)
  if (c.pulseClear > 0 && c.pulseClear < DISC_INSERTED_PULSE_THRESHOLD) {
    c.isDetected = true;
  }

  return c;
}

int matchDiscColor(float nr, float ng, float nb) {
  int bestMatch = -1;
  float minDistance = 999.0f;

  for (size_t i = 0; i < NUM_DISCS; i++) {
    float dr = nr - discDatabase[i].normR;
    float dg = ng - discDatabase[i].normG;
    float db = nb - discDatabase[i].normB;
    float dist = sqrt(dr * dr + dg * dg + db * db);

    if (dist < discDatabase[i].tolerance && dist < minDistance) {
      minDistance = dist;
      bestMatch = i;
    }
  }
  return bestMatch;
}

// ============================================================================
// 9. KONTROL AUDIO (PLAY & STOP)
// ============================================================================
void stopTrack() {
  if (currentState == STATE_PLAYING) {
    Serial.println("[JUKEBOX] Musik dihentikan.");
    if (currentTrackFile) {
      currentTrackFile.close();
    }
    currentPlayingIndex = -1;
    isTrackFileEof = false;

    // Bersihkan ring buffer
    if (audioRingBuffer != nullptr) {
      size_t dummySize;
      void *dummy;
      while ((dummy = xRingbufferReceiveUpTo(audioRingBuffer, &dummySize, 0, 4096)) != nullptr) {
        vRingbufferReturnItem(audioRingBuffer, dummy);
      }
    }

    currentState = isBtConnected ? STATE_IDLE_WAIT_DISC : STATE_WAIT_BLUETOOTH;
  }
}

void startTrackByPath(const char* path) {
  Serial.printf("[JUKEBOX] Memutar track audio: %s\n", path);

  stopTrack();

  currentTrackFile = LittleFS.open(path, "r");
  if (!currentTrackFile) {
    if (LittleFS.exists("/moogcity.mp3")) {
      Serial.printf("[FALLBACK] File %s belum ada. Memutar /moogcity.mp3 untuk demo audio!\n", path);
      currentTrackFile = LittleFS.open("/moogcity.mp3", "r");
    } else {
      Serial.printf("[ERROR] File %s tidak ditemukan di Flash LittleFS!\n", path);
      return;
    }
  }

  // Reset status dekoder MP3
  mp3Decoder.begin();
  isTrackFileEof = false;
  currentState = STATE_PLAYING;
}

void startTrack(int discIndex) {
  if (discIndex < 0 || discIndex >= (int)NUM_DISCS) return;
  Serial.printf("[JUKEBOX] Kaset: %s\n", discDatabase[discIndex].trackName);
  currentPlayingIndex = discIndex;
  startTrackByPath(discDatabase[discIndex].filePath);
}

// ============================================================================
// 10. SETUP SISTEM
// ============================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n==================================================");
  Serial.println("  MINECRAFT JUKEBOX ESP32 (TCS3000 / TCS3200)     ");
  Serial.println("  Target Speaker: YMX-868BT [12:11:8A:1A:2A:08]   ");
  Serial.println("==================================================");

  // Inisialisasi Ring Buffer Audio
  audioRingBuffer = xRingbufferCreate(AUDIO_RINGBUF_SIZE, RINGBUF_TYPE_BYTEBUF);
  if (audioRingBuffer == nullptr) {
    Serial.println("[ERROR] Gagal mengalokasikan Audio RingBuffer di RAM!");
  } else {
    Serial.printf("[OK] Audio RingBuffer dialokasikan: %u Bytes.\n", AUDIO_RINGBUF_SIZE);
  }

  // Inisialisasi Helix MP3 Decoder
  mp3Decoder.setDataCallback(mp3DataCallback);
  mp3Decoder.begin();
  Serial.println("[OK] Helix MP3 Decoder siap.");

  // Inisialisasi Pin TCS3000
  pinMode(S0_PIN, OUTPUT);
  pinMode(S1_PIN, OUTPUT);
  pinMode(S2_PIN, OUTPUT);
  pinMode(S3_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(OUT_PIN, INPUT);

  digitalWrite(S0_PIN, HIGH);
  digitalWrite(S1_PIN, LOW);   // 20% frequency scale
  digitalWrite(LED_PIN, HIGH);  // Nyalakan LED penerangan sensor
  Serial.println("[OK] Sensor TCS3000 diinisialisasi (LED ON).");

  // Inisialisasi LittleFS Flash Internal
  if (!LittleFS.begin(true)) {
    Serial.println("[ERROR] Gagal me-mount LittleFS!");
  } else {
    Serial.println("[OK] LittleFS Flash Internal siap.");
  }

  // Konfigurasi Bluetooth A2DP Source
  Serial.println("[BT] Menyiapkan modul Bluetooth Classic A2DP Source...");
  a2dp_source.set_ssp_enabled(true);                        // Secure Simple Pairing
  a2dp_source.set_pin_code("0000", ESP_BT_PIN_TYPE_FIXED); // PIN modul YMX-868BT
  a2dp_source.set_valid_cod_service(0xFFFF);                // Buka semua jenis COD
  a2dp_source.set_auto_reconnect(TARGET_SPEAKER_MAC, 10);   // Langsung sambungkan ke MAC 12:11:8A:1A:2A:08
  a2dp_source.set_ssid_callback(bt_ssid_callback);          // Fallback scan jika diperlukan
  a2dp_source.set_on_connection_state_changed(bt_connection_state_callback);
  a2dp_source.set_volume((currentVolume * 127) / 100);

  Serial.printf("[BT] Menghubungkan langsung ke target: %s [12:11:8A:1A:2A:08]...\n", BT_SPEAKER_NAME);
  a2dp_source.start(BT_SPEAKER_NAME, get_sound_data);

  Serial.println("[READY] ESP32 Jukebox Boot Selesai!");
}

// ============================================================================
// 11. MAIN LOOP
// ============================================================================
void loop() {
  unsigned long now = millis();

  // 1. Status log berkala jika Bluetooth belum tersambung
  if (!isBtConnected && (now - lastBtStatusLog >= 4000)) {
    lastBtStatusLog = now;
    Serial.printf("[BT CONNECTING] Menunggu speaker YMX-868BT [12:11:8A:1A:2A:08]... Pastikan speaker menyala!\n");
  }

  // 2. Dekode Audio MP3 di background saat lagu sedang dimainkan
  if (currentState == STATE_PLAYING && currentTrackFile && currentTrackFile.available()) {
    if (audioRingBuffer != nullptr && xRingbufferGetCurFreeSize(audioRingBuffer) > 2048) {
      size_t bytesRead = currentTrackFile.read(mp3ReadBuffer, sizeof(mp3ReadBuffer));
      if (bytesRead > 0) {
        mp3Decoder.write(mp3ReadBuffer, bytesRead);
      }
      if (!currentTrackFile.available()) {
        isTrackFileEof = true;
      }
    }
  }

  // 3. Pembacaan Sensor Warna Setiap 100 ms
  if (now - lastSensorReadTime >= 100) {
    lastSensorReadTime = now;
    ColorReading c = readTCS3000();

#if CALIBRATION_MODE
    Serial.printf("[CALIB] R:%4u G:%4u B:%4u Clear:%4u us | Norm: r=%.2f g=%.2f b=%.2f | Disc: %s\n",
                  c.pulseR, c.pulseG, c.pulseB, c.pulseClear, c.normR, c.normG, c.normB,
                  c.isDetected ? "TERDETEKSI" : "KOSONG");
    return;
#endif

    // Deteksi kaset dimasukkan ke slot
    if (c.isDetected && !isDiscPresent) {
      if (debounceStartTime == 0) {
        debounceStartTime = now;
      } else if (now - debounceStartTime > 350) {
        isDiscPresent = true;
        debounceStartTime = 0;
        Serial.printf("[SENSOR] Kaset terdeteksi! (Clear Pulse: %u us)\n", c.pulseClear);

        int discMatch = matchDiscColor(c.normR, c.normG, c.normB);
        if (discMatch >= 0) {
          Serial.printf("[SENSOR] Kaset Dikenali: %s!\n", discDatabase[discMatch].trackName);
          startTrack(discMatch);
        } else {
          Serial.printf("[SENSOR] Kaset Belum Terkalibrasi (r=%.2f, g=%.2f, b=%.2f). Memutar track default...\n",
                        c.normR, c.normG, c.normB);
          // Jika warna belum terkalibrasi pas, putar track pertama atau moogcity agar ada suara
          startTrack(0);
        }
      }
    } 
    // Deteksi kaset dicabut dari slot
    else if (!c.isDetected && isDiscPresent) {
      if (debounceStartTime == 0) {
        debounceStartTime = now;
      } else if (now - debounceStartTime > 250) {
        isDiscPresent = false;
        debounceStartTime = 0;
        Serial.println("[SENSOR] Kaset dicabut dari slot.");
        stopTrack();
      }
    } 
    else {
      debounceStartTime = 0;
    }
  }

  // 4. Pembacaan Serial Command dari Localhost Web Dashboard / Serial Monitor
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      Serial.printf("[CMD] Diterima perintah: %s\n", cmd.c_str());
      if (cmd.equalsIgnoreCase("PLAY") || cmd.equalsIgnoreCase("P")) {
        startTrackByPath("/moogcity.mp3");
      } else if (cmd.startsWith("PLAY:") || cmd.startsWith("play:")) {
        String track = cmd.substring(5);
        track.trim();
        if (!track.startsWith("/")) track = "/" + track;
        if (!track.endsWith(".mp3")) track += ".mp3";
        startTrackByPath(track.c_str());
      } else if (cmd.equalsIgnoreCase("STOP") || cmd.equalsIgnoreCase("S")) {
        stopTrack();
      } else if (cmd.startsWith("VOL:") || cmd.startsWith("vol:")) {
        int volPercent = cmd.substring(4).toInt();
        currentVolume = constrain(volPercent, 0, 100);
        int rawVol = (currentVolume * 127) / 100;
        a2dp_source.set_volume(rawVol);
        Serial.printf("[VOLUME] Volume disetel ke: %d%% (raw: %d)\n", currentVolume, rawVol);
      } else if (cmd.equalsIgnoreCase("STATUS")) {
        Serial.printf("{\"bt\":%d,\"state\":%d,\"track\":\"%s\",\"eof\":%d,\"vol\":%d}\n",
                      isBtConnected ? 1 : 0, (int)currentState,
                      currentTrackFile ? currentTrackFile.name() : "NONE",
                      isTrackFileEof ? 1 : 0, currentVolume);
      }
    }
  }

  delay(5);
}

