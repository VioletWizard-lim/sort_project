# 카드 정렬 확인 프로그램 - ESP32 (MicroPython) 쪽 코드
#
# Thonny 에서 이 파일을 열고 "다른 이름으로 저장 → MicroPython 장치" 에 main.py 로 저장한다.
# ESP32 가 켜질 때마다 자동으로 실행된다.
#
# PC 프로그램(board.py)이 USB 로 보내는 명령을 받아 RGB LED 와 I2C LCD 를 제어한다.
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

import sys
import time

from machine import I2C, PWM, Pin

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


print("BOOT sort_board")
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
    print("READY sort_board LCD=" + ("0x%02X" % lcd_address if lcd else "none"))


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


send_ready()
while True:
    line = sys.stdin.readline()
    try:
        handle(line.strip("\r\n"))
    except (ValueError, OSError) as e:
        print("ERROR " + repr(e))
