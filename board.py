"""아두이노 우노 보드 (RGB LED 9·10·11번 핀, I2C LCD 16x2).

보드에는 arduino/sort_board/sort_board.ino 를 올려야 한다.
시리얼로 한 줄씩 명령을 보낸다.
    L,r,g,b          RGB LED 색 (0~255)
    C                LCD 지우기
    P,col,row,text   LCD (col, row) 위치에 글자 쓰기
보드를 찾지 못하면 콘솔과 카메라 창에만 LED/LCD 상태를 보여준다.
"""
import threading
import time

LCD_COLS = 16


def find_arduino_port():
    from serial.tools import list_ports
    for port in list_ports.comports():
        desc = f"{port.description} {port.manufacturer or ''}".lower()
        if any(name in desc for name in ("arduino", "ch340", "ch910", "usb serial", "usb-serial")):
            return port.device
    return None


class Board:
    def __init__(self, port="auto", baud=9600):
        self.led = (0, 0, 0)
        self.lcd_lines = ["", ""]
        self._lock = threading.Lock()
        self._serial = None

        if port in (None, "none"):
            print("[보드] 아두이노 없이 실행합니다.")
            return
        try:
            import serial
            if port == "auto":
                port = find_arduino_port()
                if port is None:
                    print("[보드] 아두이노를 찾지 못해 보드 없이 실행합니다. (--port 로 지정 가능)")
                    return
            self._serial = serial.Serial(port, baud, timeout=1)
            time.sleep(2)  # 포트를 열면 우노가 리셋되므로 잠시 기다린다
            print(f"[보드] {port} 에 연결했습니다.")
        except Exception as e:
            print(f"[보드] 연결 실패 ({e}). 보드 없이 실행합니다.")
            self._serial = None

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
