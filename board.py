"""RGB LED 와 I2C LCD(16x2)가 연결된 보드 (ESP32 또는 아두이노 우노).

ESP32 (MicroPython) 에는 Thonny 로 esp32/main.py 를 main.py 로 저장하고,
아두이노에는 arduino/sort_board/sort_board.ino 를 업로드한다. 둘 다 같은 명령을 알아듣는다.
시리얼로 한 줄씩 명령을 보낸다.
    L,r,g,b          RGB LED 색 (0~255)
    C                LCD 지우기
    P,col,row,text   LCD (col, row) 위치에 글자 쓰기
    ?                준비 신호 요청
보드는 켜지면 "READY sort_board LCD=0x27" 같은 준비 신호를 보낸다.
보드를 찾지 못하면 콘솔과 카메라 창에만 LED/LCD 상태를 보여준다.
"""
import threading
import time

LCD_COLS = 16
READY = "READY sort_board"
BOOT = "BOOT sort_board"


def wait_ready(ser, timeout=5.0, received=None):
    """보드의 준비 신호를 기다린다. 받으면 그 줄을, 못 받으면 None을 돌려준다.
    received 리스트를 주면 그동안 받은 다른 줄들을 담아 준다."""
    start = time.time()
    ask_at = [start + 0.3, start + timeout / 2]  # 바로 한 번, 응답이 없으면 중간에 한 번 더 묻는다
    while time.time() < start + timeout:
        if ask_at and time.time() >= ask_at[0]:
            ser.write(b"?\n")
            ask_at.pop(0)
        line = ser.readline().decode("ascii", "replace").strip()
        if line.startswith(READY):
            return line
        if line and received is not None:
            received.append(line)
    return None


# 아두이노 우노, ESP32 와 호환 보드에 쓰이는 USB 칩 제조사 번호
# (Arduino, CH340/CH9102, FTDI, CP210x, Espressif 내장 USB)
ARDUINO_VIDS = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4, 0x303A}


def _likely_ports_first(ports):
    """아두이노처럼 보이는 포트를 먼저 확인한다. 블루투스 포트는 뺀다.
    한국어 윈도우에서는 정품 우노가 'USB 직렬 장치'로 보이므로 이름보다 USB 번호(VID)를 먼저 본다."""
    def score(p):
        desc = f"{p.description} {p.manufacturer or ''}".lower()
        if p.vid in ARDUINO_VIDS or any(n in desc for n in ("arduino", "ch340", "usb serial", "usb-serial")):
            return 0
        return 1
    return [p.device for p in sorted(ports, key=score)
            if not any(n in (p.description or "").lower() for n in ("bluetooth", "블루투스"))]


def open_board(port, baud):
    """포트를 열고 준비 신호를 확인한다. (serial 객체, 준비 신호 줄 또는 None, 받은 다른 줄들)"""
    import serial
    ser = serial.Serial()
    ser.port, ser.baudrate, ser.timeout = port, baud, 0.5
    # ESP32 는 포트를 열 때 DTR/RTS 가 켜져 있으면 리셋/다운로드 모드에 붙잡혀 멈춘다.
    # 둘 다 끈 채로 열면 보드가 다시 시작하지 않으므로, 준비 신호는 '?' 로 물어서 받는다.
    ser.dtr = False
    ser.rts = False
    ser.open()
    received = []
    return ser, wait_ready(ser, received=received), received


class Board:
    def __init__(self, port="auto", baud=115200):
        self.led = (0, 0, 0)
        self.lcd_lines = ["", ""]
        self._lock = threading.Lock()
        self._serial = None

        if port in (None, "none"):
            print("[보드] 아두이노 없이 실행합니다.")
            return
        try:
            from serial.tools import list_ports
            ports = [port] if port != "auto" else _likely_ports_first(list_ports.comports())
        except ImportError as e:
            print(f"[보드] pyserial 이 없어 보드 없이 실행합니다 ({e})")
            return
        if not ports:
            print("[보드] 연결된 보드(COM 포트)가 없습니다. USB 케이블을 확인하세요. 보드 없이 실행합니다.")
            return

        for device in ports:
            print(f"[보드] {device} 확인 중...")
            try:
                ser, ready, received = open_board(device, baud)
            except Exception as e:
                print(f"[보드] {device} 를 열 수 없습니다 ({e})")
                continue
            if ready:
                self._serial = ser
                print(f"[보드] {device} 에 연결했습니다. ({ready})")
                if ready.endswith("LCD=none"):
                    print("[보드] LCD를 찾지 못했습니다. LCD 배선(SDA→A4, SCL→A5, VCC, GND)을 확인하세요.")
                self._self_test()
                return
            ser.close()
            if BOOT in received:
                print(f"[보드] {device}: sort_board 는 켜졌지만 LCD를 찾다가 멈췄습니다.")
                print("       LCD 배선(SDA→A4, SCL→A5, VCC→5V, GND)과 접촉을 확인하세요.")
            elif any(">>>" in line for line in received):
                print(f"[보드] {device}: ESP32 에 MicroPython 은 있지만 main.py 가 실행되고 있지 않습니다.")
                print("       Thonny 로 esp32/main.py 를 'MicroPython 장치'에 main.py 로 저장했는지 확인하고,")
                print("       Thonny 를 닫은 뒤 ESP32 의 EN(리셋) 버튼을 한 번 누르세요.")
            elif received:
                print(f"[보드] {device} 에서 준비 신호 대신 이런 내용을 받았습니다: {received[:3]}")
                print("       다른 프로그램(예: Scratch용 펌웨어)이 올라가 있는 것 같습니다.")
            else:
                print(f"[보드] {device} 에서 아무 신호도 없습니다.")

        print("[보드] sort_board 프로그램이 올라간 보드를 찾지 못했습니다.")
        print("       ESP32(MicroPython): Thonny 로 esp32/main.py 를 ESP32 에 main.py 로 저장했는지 확인하세요.")
        print("       아두이노: Arduino IDE 로 arduino/sort_board/sort_board.ino 를 업로드했는지 확인하세요.")
        print("       (Thonny 나 Arduino IDE 가 보드에 연결된 채로 열려 있으면 연결할 수 없으니 닫아 주세요.)")
        print("       보드 없이 실행합니다.")

    def _self_test(self):
        """연결되면 LED를 빨강, 초록, 파랑으로 한 번씩 켜서 배선을 확인한다."""
        for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)):
            self.rgb(color)
            time.sleep(0.3)

    def _send(self, *lines):
        if self._serial is None:
            return
        with self._lock:
            for line in lines:
                self._serial.write((line + "\n").encode("ascii", "replace"))

    def rgb(self, color):
        """RGB LED 색 정하기"""
        r, g, b = (max(0, min(255, int(c))) for c in color)
        self.led = (r, g, b)
        self._send(f"L,{r},{g},{b}")

    def lcd(self, row0="", row1=""):
        """LCD를 지우고 두 줄을 쓴다."""
        row0, row1 = str(row0)[:LCD_COLS], str(row1)[:LCD_COLS]
        self.lcd_lines = [row0, row1]
        print(f"[LCD] {row0} | {row1}")
        self._send("C", f"P,0,0,{row0}", f"P,0,1,{row1}")

    def close(self):
        if self._serial is not None:
            self.rgb((0, 0, 0))
            self._send("C")
            self._serial.close()
