import serial

PORT = "/dev/ttyUSB0"
BAUD = 115200

def parse(line):
    parts = line.strip().split(",")
    if len(parts) != 3:
        return None
    return {
        "light":    int(parts[0]),
        "temp":     float(parts[1]),
        "moisture": int(parts[2]),
    }

def display(d):
    print(
        f"Light: {d['light']}%  |  "
        f"Temp: {d['temp']:.1f}°C  |  "
        f"Moisture: {d['moisture']}%"
    )

with serial.Serial(PORT, BAUD, timeout=2) as ser:
    print(f"Listening on {PORT} at {BAUD} baud...\n")
    while True:
        raw = ser.readline().decode("utf-8", errors="ignore")
        data = parse(raw)
        if data:
            display(data)
