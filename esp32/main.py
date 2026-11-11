# 카드 정렬 확인 프로그램 - ESP32 (MicroPython) 쪽 코드
#
# Thonny 에서 이 파일을 열고 "다른 이름으로 저장 → MicroPython 장치" 에 main.py 로 저장한다.
# ESP32 가 켜질 때마다 자동으로 실행된다.
#
# PC 프로그램(board.py)이 USB 또는 블루투스(BLE)로 보내는 명령을 받아 RGB LED 와 I2C LCD 를 제어한다.
# 블루투스로 쓸 때는 USB 선 대신 보조배터리 등으로 전원만 넣으면 된다.
#   L,r,g,b          RGB LED 색 (0~255)
#   C                LCD 지우기
#   P,col,row,text   LCD (col, row) 위치에 글자 쓰기
#   ?                준비 신호 다시 보내기
# 켜지면 "BOOT sort_board" 를 보내고, LCD 를 찾은 뒤 "READY sort_board LCD=0x27" 처럼
# 준비 신호를 보낸다. (LCD 를 못 찾으면 LCD=none)
#
# 배선 (ESP32 DevKit, WROOM-32)
#   LED R -> 25, LED G -> 26, LED B -> 27, 공통 다리 -> GND
#   LCD SDA -> 21, LCD SCL -> 22, VCC -> 5V(VIN), GND -> GND
# ESP32 의 6~11번 핀은 내부 플래시용이라 쓰면 안 된다.

import select
import sys
import time

from machine import I2C, PWM, Pin

# 블루투스에 보이는 보드 이름. 한 교실에서 여러 대를 쓸 때는 보드마다 다르게 (예: sort_board_2)
BOARD_NAME = "sort_board"

PIN_R, PIN_G, PIN_B = 25, 26, 27
PIN_SDA, PIN_SCL = 21, 22
LCD_COLS = 16


class LCD:
    """PCF8574 I2C 모듈이 붙은 16x2 LCD (HD44780). 핀 배치: P0=RS P1=RW P2=E P3=백라이트 P4~P7=D4~D7"""

    RS, ENABLE, BACKLIGHT = 0x01, 0x04, 0x08

    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address
        time.sleep_ms(50)
        for wait in (5, 1, 1):          # 8비트 모드로 세 번 -> 4비트 모드로 바꾸는 정해진 순서
            self._write4(0x30)
            time.sleep_ms(wait)
        self._write4(0x20)
        self.command(0x28)  # 4비트, 2줄, 5x8 글자
        self.command(0x0C)  # 화면 켜기, 커서 끄기
        self.command(0x06)  # 글자를 쓰면 오른쪽으로 이동
        self.clear()

    def _write4(self, data):
        self.i2c.writeto(self.address, bytes([data | self.BACKLIGHT | self.ENABLE]))
        self.i2c.writeto(self.address, bytes([data | self.BACKLIGHT]))

    def _send(self, value, mode):
        self._write4((value & 0xF0) | mode)
        self._write4(((value << 4) & 0xF0) | mode)

    def command(self, value):
        self._send(value, 0)

    def clear(self):
        self.command(0x01)
        time.sleep_ms(2)

    def move_to(self, col, row):
        self.command(0x80 | (col + (0x40 if row else 0)))

    def write(self, text):
        for ch in text:
            code = ord(ch)
            self._send(code if code < 128 else ord("?"), self.RS)


def find_lcd(i2c):
    """I2C 버스를 훑어서 LCD 주소를 찾는다 (보통 0x27, 0x3F, 0x20). 없으면 None."""
    try:
        found = i2c.scan()
    except OSError:
        return None
    for address in found:
        if 0x20 <= address <= 0x27 or 0x38 <= address <= 0x3F:
            return address
    return found[0] if found else None


def make_pwm(pin):
    pwm = PWM(Pin(pin), freq=5000)
    pwm.duty_u16(0)
    return pwm


leds = [make_pwm(p) for p in (PIN_R, PIN_G, PIN_B)]


def set_rgb(r, g, b):
    for pwm, value in zip(leds, (r, g, b)):
        value = max(0, min(255, value))
        pwm.duty_u16(value * 257)  # 0~255 -> 0~65535


class BLEUart:
    """블루투스(BLE)로 시리얼 통신처럼 한 줄씩 주고받는다. (Nordic UART 서비스: 널리 쓰이는 표준 방식)"""

    SERVICE = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    RX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # PC -> 보드
    TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # 보드 -> PC
    CONNECT, DISCONNECT, WRITE = 1, 2, 3          # 블루투스 이벤트 번호

    def __init__(self, name):
        import bluetooth
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        try:
            self.ble.config(gap_name=name)
        except Exception:
            pass
        service = bluetooth.UUID(self.SERVICE)
        tx = (bluetooth.UUID(self.TX), bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY)
        rx = (bluetooth.UUID(self.RX), bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE)
        ((self.tx, self.rx),) = self.ble.gatts_register_services(((service, (tx, rx)),))
        self.ble.gatts_set_buffer(self.rx, 128, True)
        self.connections = set()
        self.received = b""
        encoded = name.encode()
        # 광고: 이름은 기본 광고에, 서비스 번호는 PC 가 물어볼 때(스캔 응답) 알려 준다
        self.adv = b"\x02\x01\x06" + bytes((len(encoded) + 1, 0x09)) + encoded
        self.resp = bytes((17, 0x07)) + bytes(service)
        self.ble.irq(self._irq)
        self.advertise()

    def advertise(self):
        self.ble.gap_advertise(100000, adv_data=self.adv, resp_data=self.resp)

    def _irq(self, event, data):
        if event == self.CONNECT:
            self.connections.add(data[0])
        elif event == self.DISCONNECT:
            self.connections.discard(data[0])
            self.advertise()  # 끊기면 다시 찾을 수 있게 한다
        elif event == self.WRITE and data[1] == self.rx:
            self.received += self.ble.gatts_read(self.rx)

    def lines(self):
        """받은 내용 중 끝난 줄들"""
        lines = []
        while b"\n" in self.received:
            line, self.received = self.received.split(b"\n", 1)
            lines.append(line.decode().strip("\r"))
        return lines

    def send(self, text):
        data = text.encode()
        for conn in list(self.connections):
            for i in range(0, len(data), 20):  # 블루투스는 한 번에 20바이트씩 보낸다
                self.ble.gatts_notify(conn, self.tx, data[i:i + 20])


uart = None


def reply(text):
    """USB 와 블루투스 양쪽으로 한 줄을 보낸다."""
    print(text)
    if uart:
        try:
            uart.send(text + "\n")
        except OSError:
            pass


reply("BOOT sort_board")
set_rgb(0, 0, 0)

i2c = I2C(0, scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=100000)
lcd_address = find_lcd(i2c)
lcd = None
if lcd_address is not None:
    try:
        lcd = LCD(i2c, lcd_address)
        lcd.write("Ready")
    except OSError:
        lcd = None


def send_ready():
    reply("READY sort_board LCD=" + ("0x%02X" % lcd_address if lcd else "none"))


def handle(cmd):
    if not cmd:
        return
    kind = cmd[0]
    if kind == "?":
        send_ready()
    elif kind == "L":
        r, g, b = (int(v) for v in cmd[2:].split(","))
        set_rgb(r, g, b)
    elif lcd is None:
        return
    elif kind == "C":
        lcd.clear()
    elif kind == "P":
        col, row, text = cmd[2:].split(",", 2)
        lcd.move_to(int(col), int(row))
        lcd.write(text[:LCD_COLS])


def run(line):
    try:
        handle(line)
    except (ValueError, OSError) as e:
        reply("ERROR " + repr(e))


try:
    uart = BLEUart(BOARD_NAME)
    print("BLE on: " + BOARD_NAME)  # Thonny 셸에서 블루투스가 켜졌는지 확인할 수 있다
except Exception as e:  # 블루투스가 없는 보드에서도 USB 로는 쓸 수 있게 한다
    print("BLE off: " + repr(e))

send_ready()
usb = select.poll()
usb.register(sys.stdin, select.POLLIN)
usb_line = ""
while True:
    # USB 와 블루투스를 번갈아 확인한다
    if usb.poll(20):
        ch = sys.stdin.read(1)
        if ch == "\n":
            run(usb_line)
            usb_line = ""
        elif ch != "\r":
            usb_line += ch
    if uart:
        for line in uart.lines():
            run(line)
