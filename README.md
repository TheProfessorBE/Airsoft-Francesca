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

---

## Reset sequence

To reset both scores to zero without power-cycling, flip the switch through this sequence — **each step must complete within 3 seconds**:

```
RED → (neutral) → BLUE → (neutral) → RED → (neutral)
```

The final neutral is the confirmation trigger. The Arduino zeroes both counters, updates the displays, and notifies the GUI.

> The switch physically passes through neutral between positions, so the sequence is: flip to Red, flip back, flip to Blue, flip back, flip to Red, flip back.

---

## Arduino sketch

Located in [`FranceskaArduino/FranceskaArduino/FranceskaArduino.ino`](FranceskaArduino/FranceskaArduino/FranceskaArduino.ino).

**Required library:** `TM1637` by Avishay Orpaz — install via Arduino IDE Library Manager.

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
