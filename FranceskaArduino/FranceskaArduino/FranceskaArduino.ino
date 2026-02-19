// Hardpoint Airsoft Gamemode
// Three-way switch wiring:
//   COM -> GND
//   A   -> D2  (PIN_SW_A) = Red team
//   B   -> D3  (PIN_SW_B) = Blue team
//
// TM1637 displays:
//   Red  display: DIO=D4, CLK=D5
//   Blue display: DIO=D6, CLK=D7
//
// Reset sequence (switch must always pass through neutral):
//   RED → (neutral) → BLUE → (neutral) → RED → (neutral = confirm)
//   Each step must complete within RESET_STEP_MS.

#include <TM1637Display.h>

// ── Pins ────────────────────────────────────────────────────────────────────
const int PIN_SW_A = D2;
const int PIN_SW_B = D3;

// TM1637Display(CLK, DIO)
TM1637Display redDisplay(D5, D4);
TM1637Display blueDisplay(D7, D6);

// ── Timing constants ────────────────────────────────────────────────────────
const unsigned long TICK_MS         = 1000;  // score tick interval
const unsigned long DEBOUNCE_MS     = 30;    // switch debounce window
const unsigned long RESET_STEP_MS   = 3000;  // max time allowed between reset steps

// ── Switch positions ─────────────────────────────────────────────────────────
enum SwitchPosition : uint8_t {
  SW_RED,
  SW_NEUTRAL,
  SW_BLUE
};

// ── Scores ──────────────────────────────────────────────────────────────────
unsigned long redScore  = 0;
unsigned long blueScore = 0;

// ── Debounce state ──────────────────────────────────────────────────────────
SwitchPosition rawPos       = SW_NEUTRAL;
SwitchPosition debouncedPos = SW_NEUTRAL;
unsigned long  debounceTimer = 0;

// ── Game state ───────────────────────────────────────────────────────────────
unsigned long lastTick = 0;

// ── Reset sequence state ─────────────────────────────────────────────────────
// Steps track only non-neutral positions: RED(1) → BLUE(2) → RED(3) → NEUTRAL(trigger)
uint8_t       resetStep  = 0;
unsigned long resetTimer = 0;

// ── Helpers ──────────────────────────────────────────────────────────────────

SwitchPosition readRaw() {
  bool a = digitalRead(PIN_SW_A) == LOW;
  bool b = digitalRead(PIN_SW_B) == LOW;
  if (a && !b) return SW_RED;
  if (!a && b) return SW_BLUE;
  return SW_NEUTRAL;
}

// Call every loop(); returns true if the debounced position just changed.
bool updateDebounce() {
  SwitchPosition raw = readRaw();
  unsigned long  now = millis();

  if (raw != rawPos) {
    rawPos       = raw;
    debounceTimer = now;          // restart the stability timer
  }

  if ((now - debounceTimer >= DEBOUNCE_MS) && (rawPos != debouncedPos)) {
    debouncedPos = rawPos;
    return true;                  // stable new position
  }
  return false;
}

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
  Serial.print("RED: ");   Serial.print(redScore);
  Serial.print("s  |  BLUE: "); Serial.print(blueScore);
  Serial.print("s  |  Holding: "); Serial.println(holder);
}

void doReset() {
  redScore  = 0;
  blueScore = 0;
  updateDisplays();
  Serial.println(">> SCORES RESET");
  printStatus();
}

// ── Reset sequence detector ──────────────────────────────────────────────────
// Called whenever the debounced position changes.
// Sequence of non-neutral positions: RED → BLUE → RED, confirmed by final NEUTRAL.
// Neutrals between steps are mechanically unavoidable and ignored.
void checkResetSequence(SwitchPosition pos) {
  unsigned long now = millis();

  // Timeout: too long since last step → back to idle
  if (resetStep > 0 && (now - resetTimer) > RESET_STEP_MS) {
    resetStep = 0;
  }

  if (pos == SW_NEUTRAL) {
    if (resetStep == 3) {
      doReset();
      resetStep = 0;
    }
    // Any other neutral is just a pass-through; ignore it.
    return;
  }

  // Non-neutral position
  switch (resetStep) {
    case 0:
      if (pos == SW_RED)  { resetStep = 1; resetTimer = now; }
      break;

    case 1:
      if (pos == SW_BLUE) { resetStep = 2; resetTimer = now; }
      else                { resetStep = 0; }  // went RED→RED? abort
      break;

    case 2:
      if (pos == SW_RED)  { resetStep = 3; resetTimer = now; }
      else                { resetStep = 0; }  // went BLUE→BLUE? abort
      break;

    case 3:
      // Waiting for final neutral; any non-neutral here aborts
      resetStep = 0;
      break;
  }
}

// ── Setup ────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  pinMode(PIN_SW_A, INPUT_PULLUP);
  pinMode(PIN_SW_B, INPUT_PULLUP);

  redDisplay.setBrightness(0x0f);
  blueDisplay.setBrightness(0x0f);
  updateDisplays();

  lastTick = millis();
  Serial.println("=== HARDPOINT STARTED ===");
  printStatus();
}

// ── Loop ─────────────────────────────────────────────────────────────────────
void loop() {
  unsigned long now        = millis();
  bool          posChanged = updateDebounce();

  if (posChanged) {
    checkResetSequence(debouncedPos);

    // Always announce; posChanged already guarantees the position is new
    switch (debouncedPos) {
      case SW_RED:     Serial.println(">> RED holds");     break;
      case SW_NEUTRAL: Serial.println(">> Contested");      break;
      case SW_BLUE:    Serial.println(">> BLUE holds");     break;
    }
  }

  // Score tick every second
  if (now - lastTick >= TICK_MS) {
    lastTick += TICK_MS;
    if (debouncedPos == SW_RED)  redScore++;
    if (debouncedPos == SW_BLUE) blueScore++;
    updateDisplays();
    printStatus();
  }
}
