# Hardpoint: Franceska

Airsoft hardpoint gamemode controller.
Two teams — Red and Blue — compete to hold a single capture point. Time spent holding the point is tracked and displayed in real time.

---

## Hardware

| Component | Details |
|---|---|
| Microcontroller | Seeed XIAO RP2040 |
| Switch | On-Off-On three-way switch |
| Displays | 2× TM1637 4-digit 7-segment |
| Audio | DFPlayer Mini + SD card + speaker (4–8 Ω) |

### Wiring

**Switch**
```
COM  →  GND
A    →  D2   (Red team)
B    →  D3   (Blue team)
```

**Red display (TM1637)**
```
DIO  →  D4
CLK  →  D5
VCC  →  3.3V
GND  →  GND
```

**Blue display (TM1637)**
```
DIO  →  D6
CLK  →  D7
VCC  →  3.3V
GND  →  GND
```

**DFPlayer Mini**
```
VCC  →  VBUS (5V from USB)
GND  →  GND
TX   →  D10  (Arduino RX, direct)
RX   →  D8   (Arduino TX, via 1kΩ resistor)
BUSY →  D9   (LOW = playing, HIGH = idle)
SPK1/SPK2 → speaker (4–8 Ω)
```

---

## How it works

- Switch to **Red** → Red team's timer counts up (seconds), shown on Red display
- Switch to **Blue** → Blue team's timer counts up, shown on Blue display
- Switch in **middle (neutral)** → both timers pause; point is contested

Scores are sent over serial every second in the format:
```
RED: 42s  |  BLUE: 17s  |  Holding: RED
```

The Python GUI reads this and displays it on screen.

### Voice announcements

Audio clips are queued and played in order. Each clip waits for the previous one to finish before starting.

| File | Trigger |
|---|---|
| `0001.mp3` | Switch flips to Red — *"Red has the hardpoint"* |
| `0002.mp3` | Switch flips to Blue — *"Blue has the hardpoint"* |
| `0003.mp3` | Red score overtakes Blue — *"Red in the lead"* |
| `0004.mp3` | Blue score overtakes Red — *"Blue in the lead"* |

Place the files in a folder named `mp3` on the SD card root:
```
SD card
└── mp3/
    ├── 0001.mp3
    ├── 0002.mp3
    ├── 0003.mp3
    └── 0004.mp3
```

---

## Reset sequence

To reset both scores to zero without power-cycling, flip the switch through this sequence — **each step must complete within 3 seconds**:

```
RED → (neutral) → BLUE → (neutral) → RED → (neutral)
```

The final neutral is the confirmation trigger. The Arduino zeroes both counters, clears the audio queue, updates the displays, and notifies the GUI.

> The switch physically passes through neutral between positions, so the sequence is: flip to Red, flip back, flip to Blue, flip back, flip to Red, flip back.

---

## Arduino sketch

Located in [`FranceskaArduino/FranceskaArduino/FranceskaArduino.ino`](FranceskaArduino/FranceskaArduino/FranceskaArduino.ino).

**Required libraries** — install via Arduino IDE Library Manager:

| Library | Author |
|---|---|
| `TM1637` | Avishay Orpaz |
| `DFRobotDFPlayerMini` | DFRobot |
| `SerialPIO` | Built into the arduino-pico framework |

**Timing constants** (top of sketch):

| Constant | Default | Description |
|---|---|---|
| `TICK_MS` | 1000 ms | Score increment interval |
| `DEBOUNCE_MS` | 30 ms | Switch debounce window |
| `RESET_STEP_MS` | 3000 ms | Max time between reset sequence steps |

---

## Python GUI

Located in [`FranceskaGUI/franceska_gui.py`](FranceskaGUI/franceska_gui.py).

**Install dependencies:**
```bash
pip install -r FranceskaGUI/requirements.txt
```

**Run:**
```bash
python FranceskaGUI/franceska_gui.py          # auto-detects Arduino
python FranceskaGUI/franceska_gui.py COM3     # specify port manually
```

The GUI auto-detects the Arduino by looking for CH340/CP210x/Arduino in the port description. The COM port can also be changed at runtime via **Serial → Select Port** in the menu bar.
