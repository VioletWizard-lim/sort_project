"""RGB LED 와 I2C LCD(16x2)가 연결된 보드 (ESP32 또는 아두이노 우노).

ESP32 (MicroPython) 에는 Thonny 로 esp32/main.py 를 main.py 로 저장하고,
아두이노에는 arduino/sort_board/sort_board.ino 를 업로드한다. 둘 다 같은 명령을 알아듣는다.
USB(시리얼) 또는 블루투스(BLE, ESP32 만)로 한 줄씩 명령을 보낸다.
    L,r,g,b          RGB LED 색 (0~255)
    C                LCD 지우기
    P,col,row,text   LCD (col, row) 위치에 글자 쓰기
    ?                준비 신호 요청
보드는 켜지면 "READY sort_board LCD=0x27" 같은 준비 신호를 보낸다.
보드를 찾지 못하면 콘솔과 카메라 창에만 LED/LCD 상태를 보여준다.
"""
import queue
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


# 블루투스(BLE)로 시리얼 통신처럼 주고받는 표준 방식 (Nordic UART 서비스). esp32/main.py 와 같은 번호
BLE_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # PC -> 보드
BLE_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # 보드 -> PC
BLE_CHUNK = 20  # 블루투스는 한 번에 20바이트씩 보낸다


class BleLink:
    """블루투스(BLE)로 보드와 주고받는다. 시리얼 포트처럼 write / readline / close 로 쓴다.

    bleak 은 비동기(asyncio)로 동작하므로, 따로 스레드를 하나 띄워 그 안에서 돌린다.
    """

    def __init__(self, name, scan_timeout=8.0):
        import asyncio
        from bleak import BleakClient, BleakScanner
        self._asyncio = asyncio
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._lines = queue.Queue()
        self._buffer = b""
        self._client = None
        try:
            device = self._run(BleakScanner.find_device_by_filter(
                lambda d, adv: name in (d.name, adv.local_name), timeout=scan_timeout), scan_timeout + 5)
            if device is None:
                raise LookupError(f"블루투스에서 '{name}' 을(를) 찾지 못했습니다")
            self._client = BleakClient(device)
            self._run(self._client.connect(), 20)
            self._run(self._client.start_notify(BLE_TX, self._on_notify), 10)
        except BaseException:
            self.close()
            raise

    def _run(self, coroutine, timeout):
        return self._asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(timeout)

    def _on_notify(self, _sender, data):
        self._buffer += bytes(data)
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            self._lines.put(line + b"\n")

    def readline(self):
        try:
            return self._lines.get(timeout=0.5)
        except queue.Empty:
            return b""

    def write(self, data):
        for i in range(0, len(data), BLE_CHUNK):
            self._run(self._client.write_gatt_char(BLE_RX, data[i:i + BLE_CHUNK], response=True), 5)

    def close(self):
        if self._client is not None:
            try:
                self._run(self._client.disconnect(), 5)
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)


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
    ready = wait_ready(ser, timeout=2.5, received=received)
    if ready or received:
        return ser, ready, received

    # 아무 응답이 없을 때
    # - ESP32 보드 자체 USB(ESP32-S2/S3/C3)는 DTR 이 켜져야 글자를 보낸다.
    #   (보통 ESP32 는 RTS 가 꺼져 있으면 DTR 을 켜도 다시 시작하지 않는다)
    # - Thonny 가 MicroPython 을 멈춰 둔 상태(raw REPL)로 남아 있으면 아무 대답도 하지 않는다.
    #   Ctrl-C(멈춤), Ctrl-B(raw REPL 나가기), Ctrl-D(소프트 리셋)를 보내 main.py 를 다시 실행시킨다.
    #   아두이노에는 알아듣지 못하는 한 줄로 지나간다. (끝의 줄바꿈으로 그 줄을 끝낸다)
    try:
        ser.dtr = True
    except Exception:  # DTR 을 지원하지 않는 장치도 있다
        pass
    for key in (b"\x03\x03", b"\x02", b"\x04", b"\n"):
        ser.write(key)
        time.sleep(0.2)
    ready = wait_ready(ser, timeout=5.0, received=received)
    return ser, ready, received


class Board:
    def __init__(self, port="auto", baud=115200, ble_name="sort_board"):
        """port: auto(USB 먼저, 없으면 블루투스) / ble(블루투스만) / COM3 같은 포트 이름 / none"""
        self.led = (0, 0, 0)
        self.lcd_lines = ["", ""]
        self._lock = threading.Lock()
        self._serial = None  # USB 시리얼 또는 BleLink

        if port in (None, "none"):
            print("[보드] 보드 없이 실행합니다.")
            return
        if port != "ble" and self._connect_usb(port, baud):
            return
        if port in ("auto", "ble") and self._connect_ble(ble_name):
            return

        print("[보드] sort_board 프로그램이 올라간 보드를 찾지 못했습니다.")
        print("       ESP32(MicroPython): Thonny 로 esp32/main.py 를 ESP32 에 main.py 로 저장했는지 확인하세요.")
        print("       아두이노: Arduino IDE 로 arduino/sort_board/sort_board.ino 를 업로드했는지 확인하세요.")
        print("       (Thonny 나 Arduino IDE 가 보드에 연결된 채로 열려 있으면 연결할 수 없으니 닫아 주세요.)")
        print("       보드 없이 실행합니다.")

    def _connected(self, link, where, ready):
        self._serial = link
        print(f"[보드] {where} 에 연결했습니다. ({ready})")
        if ready.endswith("LCD=none"):
            print("[보드] LCD를 찾지 못했습니다. LCD 배선(SDA, SCL, VCC, GND)을 확인하세요.")
        self._self_test()

    def _connect_usb(self, port, baud):
        try:
            from serial.tools import list_ports
            ports = [port] if port != "auto" else _likely_ports_first(list_ports.comports())
        except ImportError as e:
            print(f"[보드] pyserial 이 없어 USB 로는 연결할 수 없습니다 ({e})")
            return False
        if not ports:
            print("[보드] USB 로 연결된 보드(COM 포트)가 없습니다.")
            return False

        for device in ports:
            print(f"[보드] {device} 확인 중...")
            try:
                ser, ready, received = open_board(device, baud)
            except Exception as e:
                print(f"[보드] {device} 를 열 수 없습니다 ({e})")
                continue
            if ready:
                self._connected(ser, device, ready)
                return True
            ser.close()
            if BOOT in received:
                print(f"[보드] {device}: sort_board 는 켜졌지만 LCD를 찾다가 멈췄습니다.")
                print("       LCD 배선(SDA, SCL, VCC→5V, GND)과 접촉을 확인하세요.")
            elif any(">>>" in line for line in received):
                print(f"[보드] {device}: ESP32 에 MicroPython 은 있지만 main.py 가 실행되고 있지 않습니다.")
                print("       Thonny 로 esp32/main.py 를 'MicroPython 장치'에 main.py 로 저장했는지 확인하고,")
                print("       Thonny 를 닫은 뒤 ESP32 의 EN(리셋) 버튼을 한 번 누르세요.")
            elif received:
                print(f"[보드] {device} 에서 준비 신호 대신 이런 내용을 받았습니다: {received[:3]}")
                print("       다른 프로그램(예: Scratch용 펌웨어)이 올라가 있는 것 같습니다.")
            else:
                print(f"[보드] {device} 에서 아무 신호도 없습니다.")
        return False

    def _connect_ble(self, name):
        print(f"[보드] 블루투스에서 '{name}' 을(를) 찾는 중... (최대 8초)")
        try:
            link = BleLink(name)
        except ImportError as e:
            print(f"[보드] 블루투스 라이브러리(bleak)가 없습니다 ({e})")
            return False
        except Exception as e:
            print(f"[보드] 블루투스 연결 실패: {e}")
            print("       ESP32 에 전원이 들어와 있는지, PC 의 블루투스가 켜져 있는지 확인하세요.")
            return False
        ready = wait_ready(link)
        if ready:
            self._connected(link, f"블루투스 '{name}'", ready)
            return True
        link.close()
        print(f"[보드] 블루투스 '{name}' 에 연결했지만 준비 신호가 없습니다.")
        return False

    def _self_test(self):
        """연결되면 LED를 빨강, 초록, 파랑으로 한 번씩 켜서 배선을 확인한다."""
        for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)):
            self.rgb(color)
            time.sleep(0.3)

    def _send(self, *lines):
        if self._serial is None:
            return
        data = "".join(line + "\n" for line in lines).encode("ascii", "replace")
        with self._lock:
            try:
                self._serial.write(data)
            except Exception as e:  # 블루투스가 끊기는 등 보드와 연락이 안 되면 화면에만 보여준다
                print(f"[보드] 보드에 보내지 못했습니다 ({e}). 보드 없이 계속합니다.")
                self._serial = None

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
        if self._serial is not None:  # 위에서 보내다 끊겼으면 이미 None
            self._serial.close()
