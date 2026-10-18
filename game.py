"""버블 정렬 카드 게임 로직.

Scratch 프로젝트 '35(final)'의 Ani 스프라이트 스크립트를 그대로 옮긴 것이다.
Scratch는 리스트 번호가 1부터 시작하지만 여기서는 0부터 센다.
화면에 보여주는 위치 번호(LCD의 'Pos 1 <-> 2')는 Scratch와 같게 1부터 보여준다.
"""
import queue
import re

NUM_CARDS = 8

OFF = (0, 0, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


class GameStopped(Exception):
    """창을 닫거나 q/ESC를 눌러 게임을 끝낼 때 사용한다."""


def parse_card(text):
    """OCR로 읽은 한 줄에서 공백을 지우고 숫자로 바꾼다. 숫자가 아니면 None. (공백제거)"""
    cleaned = text.replace(" ", "")
    if not _NUMBER.match(cleaned):
        return None
    value = float(cleaned)
    return int(value) if value.is_integer() else value


class SortGame:
    def __init__(self, view, board, triggers, stop_event, num_cards=NUM_CARDS):
        self.view = view            # 카메라 창 (say, read_text)
        self.board = board          # 아두이노 (rgb, lcd)
        self.triggers = triggers    # 스페이스바 / 음성 '확인' 신호가 들어오는 큐
        self.stop_event = stop_event
        self.num_cards = num_cards

        self.card_list = []   # 카드목록: 처음 등록한 카드들
        self.prev = []        # 이전 배열: 마지막으로 맞다고 확인된 배열
        self.pos = 0          # 비교위치: pos 와 pos+1 번째 카드를 비교
        self.end = 0          # 끝위치: pos 가 여기에 닿으면 한 바퀴 끝
        self.swaps = 0        # 교환횟수 (이번 바퀴)
        self.compares = 0     # 비교횟수
        self.wrongs = 0       # 오답횟수
        self.done = False     # 완료

    # ---------- 기본 동작 ----------

    def _sleep(self, secs):
        if self.stop_event.wait(secs):
            raise GameStopped

    def say(self, message, secs=None):
        """말하기 / ~초 동안 말하기"""
        print(f"[말풍선] {message}")
        self.view.say(message)
        if secs is not None:
            self._sleep(secs)
            self.view.say("")

    def flash(self, color, message):
        """LED를 켜고 2초 동안 말한 뒤 LED를 끈다."""
        self.board.rgb(color)
        self.say(message, 2)
        self.board.rgb(OFF)

    def wait_trigger(self):
        """스페이스바를 누르거나 '확인'이라고 말할 때까지 기다린다."""
        while True:  # 이전에 쌓인 신호는 버린다
            try:
                self.triggers.get_nowait()
            except queue.Empty:
                break
        while True:
            if self.stop_event.is_set():
                raise GameStopped
            try:
                return self.triggers.get(timeout=0.1)
            except queue.Empty:
                pass

    # ---------- 사용자 정의 블록 ----------

    def read_cards(self):
        """카드 읽기: 카메라로 숫자를 읽고 왼쪽부터 순서대로 정렬한 리스트를 돌려준다."""
        cards = []
        for text, x in self.view.read_text():
            value = parse_card(text)
            if value is None:
                continue
            # 처음 등록할 때는 숫자면 모두, 그 다음부터는 등록된 카드만 받는다
            if self.card_list and value not in self.card_list:
                continue
            cards.append((x, value))
        cards.sort(key=lambda card: card[0])  # x 좌표 순 (Scratch에서는 선택 정렬로 구현)
        return [value for _, value in cards]

    def register_cards(self):
        """처음 카드 등록"""
        self.board.lcd("Set Cards", "SPACE or VOICE")
        while True:
            self.say("카드를 놓고 스페이스바를 누르거나 확인이라고 말해주세요")
            self.wait_trigger()
            current = self.read_cards()
            if len(current) == self.num_cards:
                break
            self.say("카드가 제대로 안 보여요! 다시 눌러주세요!", 2)
        self.say("카드 인식 완료!", 2)

        self.card_list = list(current)   # 카드목록저장
        self.prev = list(current)        # 이전 배열 저장
        self.pos = 0
        self.end = len(self.card_list) - 1
        self.swaps = 0
        self.compares = 0
        self.wrongs = 0
        self.done = False
        self.show_guide()

    def show_guide(self):
        """LCD 안내: 지금 비교할 두 카드를 보여준다."""
        p = self.pos
        self.board.lcd(f"Pos {p + 1} <-> {p + 2}",
                       f"{self.prev[p]} ? {self.prev[p + 1]}")

    def should_swap(self):
        """지금 비교하는 두 카드를 바꿔야 하는지"""
        return not self.prev[self.pos] < self.prev[self.pos + 1]

    def judge(self, current):
        """정답 판정: 두 카드만 올바르게 바꿨는지 확인한다."""
        p = self.pos
        others_same = all(current[k] == self.prev[k]
                          for k in range(len(current)) if k not in (p, p + 1))
        swapped = current[p] == self.prev[p + 1] and current[p + 1] == self.prev[p]
        return others_same and swapped and self.should_swap()

    def handle_wrong(self):
        """오답처리"""
        self.wrongs += 1
        self.board.lcd("Wrong! Try again")
        self._sleep(1)
        self.show_guide()

    def next_compare(self):
        """다음 비교"""
        self.compares += 1
        self.pos += 1
        if self.pos != self.end:
            self.show_guide()
            return

        self.end -= 1
        if self.swaps == 0 or self.end == 0:
            self.celebrate()
        else:
            self.say("한바퀴 끝! 처음으로!!", 2)
            self.pos = 0
            self.swaps = 0
            self.show_guide()

    def celebrate(self):
        """정렬 완료: LCD에 결과를 띄우고 LED를 무지개색으로 계속 바꾼다."""
        self.board.lcd("SORTED!!", f"C: {self.compares} W: {self.wrongs}")
        self.say("정렬 완료!", 3)
        self.done = True
        r = g = b = 0
        while True:
            self.board.rgb((r, g, b))
            r, g, b = r + 10, g + 20, b + 30
            r = 0 if r >= 255 else r
            g = 0 if g >= 255 else g
            b = 0 if b >= 255 else b
            self._sleep(0.1)

    # ---------- 초록 깃발 ----------

    def run(self):
        try:
            self.board.rgb(OFF)
            self.register_cards()
            while not self.done:
                self.wait_trigger()
                self.step(self.read_cards())
        except GameStopped:
            pass

    def step(self, current):
        """스페이스바 / '확인' 한 번에 대한 처리"""
        if len(current) != len(self.card_list):
            self.say("카드가 제대로 안보여요!", 2)
            for _ in range(3):
                self.board.rgb(YELLOW)
                self._sleep(0.3)
                self.board.rgb(OFF)
                self._sleep(0.3)
            return

        if current != self.prev:  # 변화확인
            if self.judge(current):
                self.flash(BLUE, "정답")
                self.prev = list(current)
                self.swaps += 1
                self.next_compare()
            else:
                self.flash(RED, "틀렸어요")
                self.handle_wrong()
        elif not self.should_swap():
            self.flash(BLUE, "통과! 안 바꿔도 돼요!")
            self.next_compare()
        else:
            self.flash(RED, "바꿔야 돼요!")
            self.handle_wrong()
