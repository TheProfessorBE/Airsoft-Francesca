// Hardpoint Airsoft Gamemode
//
// ── Switch ───────────────────────────────────────────────────────────────────
//   COM → GND
//   A   → D2  (Red team)
//   B   → D3  (Blue team)
//
// ── TM1637 displays ──────────────────────────────────────────────────────────
//   Red  display: DIO=D4, CLK=D5
//   Blue display: DIO=D6, CLK=D7
//
// ── DFPlayer Mini ────────────────────────────────────────────────────────────
//   VCC  → VBUS (5V)
//   GND  → GND
//   TX   → D10  (Arduino RX, direct)
//   RX   → D8   (Arduino TX, via 1kΩ resistor)
//   BUSY → D9   (LOW = playing, HIGH = idle)
//   SPK1/SPK2 → speaker (4–8 Ω)
//
// ── SD card track list (place in /mp3/ folder) ───────────────────────────────
//   0001.mp3 → "Red has the hardpoint"
//   0002.mp3 → "Blue has the hardpoint"
//   0003.mp3 → "Red in the lead"
//   0004.mp3 → "Blue in the lead"
//
// ── Reset sequence ───────────────────────────────────────────────────────────
//   RED → (neutral) → BLUE → (neutral) → RED → (neutral = confirm)
//   Each step must complete within RESET_STEP_MS.

#include <TM1637Display.h>
#include <SerialPIO.h>
#include <DFRobotDFPlayerMini.h>

// ── Pins ─────────────────────────────────────────────────────────────────────
const int PIN_SW_A    = D2;
const int PIN_SW_B    = D3;
const int PIN_DF_BUSY = D9;

// TM1637Display(CLK, DIO)
TM1637Display redDisplay(D5, D4);
TM1637Display blueDisplay(D7, D6);

// DFPlayer serial: SerialPIO(TX, RX)
SerialPIO          dfSerial(D8, D10);
DFRobotDFPlayerMini dfPlayer;

// ── Audio tracks ─────────────────────────────────────────────────────────────
const uint8_t TRACK_RED_HOLDS  = 1;
const uint8_t TRACK_BLUE_HOLDS = 2;
const uint8_t TRACK_RED_LEAD   = 3;
const uint8_t TRACK_BLUE_LEAD  = 4;

// Circular queue — announcements wait until the current clip finishes
const uint8_t QUEUE_SIZE = 8;
uint8_t audioQueue[QUEUE_SIZE];
uint8_t queueHead = 0;
uint8_t queueTail = 0;

// ── Timing constants ─────────────────────────────────────────────────────────
const unsigned long TICK_MS       = 1000;
const unsigned long DEBOUNCE_MS   = 30;
const unsigned long RESET_STEP_MS = 3000;

// ── Switch positions ──────────────────────────────────────────────────────────
enum SwitchPosition : uint8_t { SW_RED, SW_NEUTRAL, SW_BLUE };

// ── Lead state ────────────────────────────────────────────────────────────────
enum LeadState : uint8_t { LEAD_TIED, LEAD_RED, LEAD_BLUE };

// ── Scores & state ────────────────────────────────────────────────────────────
unsigned long redScore  = 0;
unsigned long blueScore = 0;
LeadState     lastLead  = LEAD_TIED;

// ── Debounce state ────────────────────────────────────────────────────────────
SwitchPosition rawPos        = SW_NEUTRAL;
SwitchPosition debouncedPos  = SW_NEUTRAL;
unsigned long  debounceTimer = 0;

// ── Game state ────────────────────────────────────────────────────────────────
unsigned long lastTick = 0;

// ── Reset sequence state ──────────────────────────────────────────────────────
uint8_t       resetStep  = 0;
unsigned long resetTimer = 0;

// ── Audio helpers ─────────────────────────────────────────────────────────────

void queueTrack(uint8_t track) {
  uint8_t next = (queueTail + 1) % QUEUE_SIZE;
  if (next != queueHead) {          // drop silently if queue is full
    audioQueue[queueTail] = track;
    queueTail = next;
  }
}

void clearAudioQueue() {
  queueHead = queueTail = 0;
  dfPlayer.stop();
}

// Called every loop(). Starts the next queued track only when the
// DFPlayer BUSY pin goes HIGH (current clip has finished).
void updateAudio() {
  if (digitalRead(PIN_DF_BUSY) == LOW) return;  // still playing
  if (queueHead == queueTail)          return;  // nothing queued
  dfPlayer.play(audioQueue[queueHead]);
  queueHead = (queueHead + 1) % QUEUE_SIZE;
}

// ── Switch & debounce ─────────────────────────────────────────────────────────

SwitchPosition readRaw() {
  bool a = digitalRead(PIN_SW_A) == LOW;
  bool b = digitalRead(PIN_SW_B) == LOW;
  if (a && !b) return SW_RED;
  if (!a && b) return SW_BLUE;
  return SW_NEUTRAL;
}

bool updateDebounce() {
  SwitchPosition raw = readRaw();
  unsigned long  now = millis();
  if (raw != rawPos) {
    rawPos        = raw;
    debounceTimer = now;
  }
  if ((now - debounceTimer >= DEBOUNCE_MS) && (rawPos != debouncedPos)) {
    debouncedPos = rawPos;
    return true;
  }
  return false;
}

// ── Display & serial output ───────────────────────────────────────────────────

void updateDisplays() {
  redDisplay.showNumberDec(min(redScore,  9999UL), true);
  blueDisplay.showNumberDec(min(blueScore, 9999UL), true);
}

void printStatus() {
  const char* holder;
  switch (debouncedPos) {
    case SW_RED:  holder = "RED";     break;
    case SW_BLUE: holder = "BLUE";    break;
    default:      holder = "NEUTRAL"; break;
  }
  Serial.print("RED: ");        Serial.print(redScore);
  Serial.print("s  |  BLUE: "); Serial.print(blueScore);
  Serial.print("s  |  Holding: "); Serial.println(holder);
}

// ── Reset ─────────────────────────────────────────────────────────────────────

void doReset() {
  redScore  = 0;
  blueScore = 0;
  lastLead  = LEAD_TIED;
  clearAudioQueue();
  updateDisplays();
  Serial.println(">> SCORES RESET");
  printStatus();
}

// ── Reset sequence detector ───────────────────────────────────────────────────

void checkResetSequence(SwitchPosition pos) {
  unsigned long now = millis();

  if (resetStep > 0 && (now - resetTimer) > RESET_STEP_MS) {
    resetStep = 0;
  }

  if (pos == SW_NEUTRAL) {
    if (resetStep == 3) { doReset(); resetStep = 0; }
    return;
  }

  switch (resetStep) {
    case 0: if (pos == SW_RED)  { resetStep = 1; resetTimer = now; } break;
    case 1: if (pos == SW_BLUE) { resetStep = 2; resetTimer = now; }
            else                { resetStep = 0; } break;
    case 2: if (pos == SW_RED)  { resetStep = 3; resetTimer = now; }
            else                { resetStep = 0; } break;
    case 3: resetStep = 0; break;
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(9600);
  pinMode(PIN_SW_A,    INPUT_PULLUP);
  pinMode(PIN_SW_B,    INPUT_PULLUP);
  pinMode(PIN_DF_BUSY, INPUT);

  redDisplay.setBrightness(0x0f);
  blueDisplay.setBrightness(0x0f);
  updateDisplays();

  dfSerial.begin(9600);
  delay(200);                          // let DFPlayer boot
  if (dfPlayer.begin(dfSerial, false)) // false = no ACK, faster response
    dfPlayer.volume(25);               // 0–30
  else
    Serial.println(">> DFPlayer init failed");

  lastTick = millis();
  Serial.println("=== HARDPOINT STARTED ===");
  printStatus();
}

// ── Loop ──────────────────────────────────────────────────────────────────────

void loop() {
  unsigned long now        = millis();
  bool          posChanged = updateDebounce();

  updateAudio();   // pump the queue — fires next clip only when BUSY goes HIGH

  if (posChanged) {
    checkResetSequence(debouncedPos);

    switch (debouncedPos) {
      case SW_RED:
        Serial.println(">> RED holds");
        queueTrack(TRACK_RED_HOLDS);
        break;
      case SW_NEUTRAL:
        Serial.println(">> Contested");
        break;
      case SW_BLUE:
        Serial.println(">> BLUE holds");
        queueTrack(TRACK_BLUE_HOLDS);
        break;
    }
  }

  // Score tick every second
  if (now - lastTick >= TICK_MS) {
    lastTick += TICK_MS;
    if (debouncedPos == SW_RED)  redScore++;
    if (debouncedPos == SW_BLUE) blueScore++;
    updateDisplays();
    printStatus();

    // Queue a lead announcement only when the lead changes hands
    LeadState currentLead = (redScore  > blueScore) ? LEAD_RED  :
                            (blueScore > redScore)  ? LEAD_BLUE : LEAD_TIED;
    if (currentLead != lastLead && currentLead != LEAD_TIED) {
      queueTrack(currentLead == LEAD_RED ? TRACK_RED_LEAD : TRACK_BLUE_LEAD);
    }
    lastLead = currentLead;
  }
}
