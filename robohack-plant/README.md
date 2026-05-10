# RoboHack Plant — Smart Robotic Gardening System

> Built at **RoboHack 2026** — the EPFL AI Team's 36-hour robotics hackathon  
> May 8–10, 2026 · EPFL Makerspace, Lausanne, Switzerland

---

## Overview

A smart robotic gardening system that combines real-time plant health sensing with robotic arm manipulation guided by a vision-language-action model. The robot monitors soil moisture, ambient light, and temperature via an ESP32-S3, then acts autonomously — watering, adjusting plant positioning, or flagging issues — using a SO-101 arm fine-tuned with SmolVLA.

---

## Hardware

### SO-101 Robotic Arm (LeRobot)
- 6-DOF open-source arm by [TheRobotStudio](https://github.com/TheRobotStudio/SO-ARM100), partially 3D-printed during the hackathon
- STS3215 bus servos — 30 kg·cm stall torque, 360° magnetic encoders per joint
- **Teleoperation:** leader arm (human-operated) + follower arm (mirrors in real time)
- Cameras: wrist-mounted + overhead overview for scene capture

### ESP32-S3 Sensor Node
- **MCU:** ESP32-S3-DevKitC-1
- **Sensors:**
  - LDR on GPIO 4 — ambient luminosity (0–100%)
  - DS18B20 on GPIO 5 (OneWire) — soil/air temperature
  - Capacitive moisture sensor on GPIO 6 (analog) + GPIO 7 (digital threshold)
- **Indicators:**
  - RGB LED 1 (GPIO 16/15/17) — temperature status: green / orange / red
  - RGB LED 2 (GPIO 18/19/20) — moisture gradient: red (dry) → orange → green (wet)
- Serial output at 115200 baud, 500 ms polling interval

---

## AI Stack

### SmolVLA
[SmolVLA](https://huggingface.co/lerobot/smolvla_base) is a 450M-parameter Vision-Language-Action model from HuggingFace, pretrained on SO-100/SO-101 community datasets. It takes:
- Multiple camera views (wrist + overview)
- Robot joint state
- A natural language instruction (e.g. `"water the dry plant on the left"`)

and outputs motor command chunks executed on the SO-101 follower arm.

### Pipeline
```
ESP32-S3 sensor readings
        │
        ▼
  Plant health state ──► language instruction
        │                       │
        └───────────┬───────────┘
                    ▼
              SmolVLA inference
                    │
                    ▼
         SO-101 follower arm action
```

Teleoperation demos are recorded using the leader arm, uploaded to HuggingFace Hub, and used to fine-tune SmolVLA for gardening-specific tasks.

---

## Firmware

Built with [PlatformIO](https://platformio.org/) and the Arduino framework.

### Dependencies
- [`paulstoffregen/OneWire`](https://github.com/PaulStoffregen/OneWire)
- [`milesburton/DallasTemperature`](https://github.com/milesburton/Arduino-Temperature-Control-Library)

### Build & Flash
```bash
# Install PlatformIO CLI or use the VSCode extension
pio run --target upload

# Monitor serial output
pio device monitor --baud 115200
```

### Serial Output Format
```
Light: 74% | Temp: 22.3°C [ORANGE] | Moisture: 31% | DRY
```

### Local Web Dashboard
The Python dashboard is now a local webapp that keeps reading the ESP32 serial stream and renders it in the browser.

```bash
python dashboard.py
```

Then open:

```text
http://127.0.0.1:8000
```

Use the connection bar to set the serial port if needed, then click Connect.

---

## About RoboHack 2026

[RoboHack](https://epflaiteam.ch/robohack) is the EPFL AI Team's flagship robotics hackathon — a 36-hour SIEGE-format competition open to 50 selected participants from across disciplines. The **Hardware Innovation Track** challenges teams to assemble a LeRobot arm kit from scratch, calibrate it, and push it beyond baseline capabilities with original applications.

Resources provided: 3D printers, mechanical workshop, soldering stations, GPU compute.

---

## Team

Built with love, sleep deprivation, and too much EPFL coffee.

- Edik Planson
- Léo Guerin
- Fabien Pieretti
- Chloé Muliva

---

## License

MIT
