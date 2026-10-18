"""카메라 창과 글자 인식(OCR).

Scratch의 카메라 인식 화면 대신 OpenCV 창에 카메라 영상을 띄운다.
창에는 인식한 숫자 상자, 말풍선, LCD/LED 상태가 함께 표시된다.
    스페이스바  : 확인 (카드 읽기)
    q / ESC     : 종료
"""
import os
import threading

import cv2
import numpy as np

WINDOW = "Sort Cards"

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


class CardReader:
    """EasyOCR로 화면 전체에서 숫자를 읽는다."""

    def __init__(self, gpu=False):
        import easyocr
        print("[OCR] 글자 인식 모델을 불러오는 중... (처음에는 내려받느라 오래 걸려요)")
        self._reader = easyocr.Reader(["en"], gpu=gpu)

    def read(self, frame):
        """[(상자 꼭짓점 4개, 글자, 정확도), ...]"""
        return self._reader.readtext(frame, allowlist="0123456789")


def _load_font(path, size):
    from PIL import ImageFont
    for candidate in [path] + FONT_CANDIDATES:
        if candidate and os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    print("[화면] 한글 글꼴을 찾지 못해 말풍선은 콘솔에만 보여요. (--font 로 지정 가능)")
    return None


class CameraView:
    def __init__(self, source, reader, board, triggers, stop_event, font_path=None):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"카메라를 열 수 없습니다: {source}")
        self.reader = reader
        self.board = board
        self.triggers = triggers
        self.stop_event = stop_event
        self.font = _load_font(font_path, 28)

        self._lock = threading.Lock()
        self._frame = None
        self._boxes = []
        self._message = ""
        self._reading = False

    def say(self, message):
        self._message = message

    def read_text(self):
        """지금 화면의 글자를 읽어 [(글자, 왼쪽 x 좌표), ...] 로 돌려준다."""
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        if frame is None:
            return []
        self._reading = True
        try:
            results = self.reader.read(frame)
        finally:
            self._reading = False
        self._boxes = results
        return [(text, min(point[0] for point in box)) for box, text, _ in results]

    # ---------- 화면 그리기 ----------

    def _draw(self, image):
        for box, text, _ in self._boxes:
            pts = np.array(box, dtype=np.int32)
            cv2.polylines(image, [pts], True, (0, 255, 0), 2)
            x, y = pts[0]
            cv2.putText(image, text, (int(x), int(y) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        h, w = image.shape[:2]
        # LCD
        cv2.rectangle(image, (10, h - 75), (290, h - 10), (40, 80, 20), -1)
        for row, line in enumerate(self.board.lcd_lines):
            cv2.putText(image, line, (20, h - 50 + row * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 255, 180), 2)
        # LED (OpenCV는 BGR 순서)
        r, g, b = self.board.led
        cv2.circle(image, (320, h - 42), 22, (b, g, r), -1)
        cv2.circle(image, (320, h - 42), 22, (255, 255, 255), 2)

        if self._reading:
            cv2.putText(image, "Reading...", (w - 170, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
        if self._message and self.font is not None:
            image = self._draw_bubble(image, self._message)
        return image

    def _draw_bubble(self, image, message):
        from PIL import Image, ImageDraw
        pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        left, top, right, bottom = draw.textbbox((20, 20), message, font=self.font)
        draw.rounded_rectangle((left - 12, top - 10, right + 12, bottom + 10),
                               radius=12, fill="white", outline="black", width=2)
        draw.text((20, 20), message, font=self.font, fill="black")
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    # ---------- 메인 반복 (메인 스레드에서 실행) ----------

    def run(self):
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        try:
            while not self.stop_event.is_set():
                ok, frame = self.cap.read()
                if not ok:
                    if cv2.waitKey(30) & 0xFF in (27, ord("q")):
                        self.stop_event.set()
                    continue
                with self._lock:
                    self._frame = frame
                cv2.imshow(WINDOW, self._draw(frame.copy()))

                key = cv2.waitKey(1) & 0xFF
                if key == ord(" "):
                    self.triggers.put("space")
                elif key in (27, ord("q")):
                    self.stop_event.set()
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    self.stop_event.set()
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
