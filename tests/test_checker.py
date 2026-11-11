"""카메라와 아두이노 없이 정렬 확인 로직을 테스트한다.

    python -m unittest discover tests
"""
import os
import queue
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checker import BLUE, RED, SortChecker, Stopped, parse_card  # noqa: E402
from sorts import SORTS, apply, bubble_sort, selection_sort  # noqa: E402


class FakeView:
    def __init__(self):
        self.messages = []

    def say(self, message):
        if message:
            self.messages.append(message)

    def read_text(self, expected=None):
        return []


class FakeBoard:
    def __init__(self):
        self.leds = []
        self.lcd_lines = ["", ""]

    def rgb(self, color):
        self.leds.append(tuple(color))

    def lcd(self, row0="", row1=""):
        self.lcd_lines = [row0, row1]


def make_checker(cards, sort="bubble"):
    checker = SortChecker(FakeView(), FakeBoard(), queue.Queue(), threading.Event(),
                          SORTS, sort=sort, num_cards=len(cards))
    checker._sleep = lambda secs: None
    checker.celebrate = lambda: setattr(checker, "done", True)  # 무지개 반복 대신
    checker.start(cards)
    return checker


class ParseCardTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_card("1 2"), 12)
        self.assertEqual(parse_card("7"), 7)
        self.assertIsNone(parse_card("가"))
        self.assertIsNone(parse_card(""))


class SortsTest(unittest.TestCase):
    CASES = [[5, 2, 8, 1, 7, 3, 6, 4], [1, 2, 3, 4], [4, 3, 2, 1], [2, 2, 1], [1]]

    def test_steps_sort_the_cards(self):
        for name, method in SORTS.items():
            for cards in self.CASES:
                arr = list(cards)
                for step in method.make_steps(cards):
                    arr = apply(arr, step)
                self.assertEqual(arr, sorted(cards), f"{name} {cards}")

    def test_bubble_stops_after_pass_without_swap(self):
        self.assertEqual(len(bubble_sort([1, 2, 3, 4])), 3)
        self.assertEqual(len(bubble_sort([2, 1, 3, 4])), 3 + 2)


class ReadCardsTest(unittest.TestCase):
    def test_sorted_by_x_and_filtered(self):
        checker = make_checker([3, 1, 2])
        checker.view.read_text = lambda expected: [("2", 300), ("9", 50), ("3", 10), ("1", 200), ("abc", 5)]
        self.assertEqual(checker.read_cards(), [3, 1, 2])


class CheckTest(unittest.TestCase):
    def test_correct_swap(self):
        checker = make_checker([3, 1, 2])
        checker.check([1, 3, 2])
        self.assertEqual(checker.prev, [1, 3, 2])
        self.assertEqual(checker.index, 1)
        self.assertIn(BLUE, checker.board.leds)

    def test_swap_not_needed(self):
        checker = make_checker([1, 3, 2])
        checker.check([3, 1, 2])
        self.assertEqual(checker.wrongs, 1)
        self.assertEqual(checker.index, 0)
        self.assertIn(RED, checker.board.leds)

    def test_pass_without_swap(self):
        checker = make_checker([1, 3, 2])
        checker.check([1, 3, 2])
        self.assertEqual(checker.index, 1)
        self.assertEqual(checker.wrongs, 0)

    def test_should_have_swapped(self):
        checker = make_checker([3, 1, 2])
        checker.check([3, 1, 2])
        self.assertEqual(checker.wrongs, 1)
        self.assertEqual(checker.board.lcd_lines, ["Pos 1 <-> 2", "3 ? 1"])

    def test_other_cards_moved(self):
        checker = make_checker([3, 1, 2, 4])
        checker.check([1, 3, 4, 2])
        self.assertEqual(checker.wrongs, 1)
        self.assertEqual(checker.prev, [3, 1, 2, 4])

    def test_missing_card(self):
        checker = make_checker([3, 1, 2])
        checker.check([3, 1])
        self.assertEqual(checker.index, 0)
        self.assertEqual(checker.view.messages, ["카드가 제대로 안보여요!"])

    def test_student_follows_every_sort(self):
        for name in SORTS:
            cards = [5, 2, 8, 1, 7, 3, 6, 4]
            checker = make_checker(cards, name)
            arr = list(cards)
            while not checker.done:
                arr = apply(arr, checker.step)
                checker.check(list(arr))
            self.assertEqual(arr, sorted(cards), name)
            self.assertEqual(checker.wrongs, 0, name)

    def test_pass_end_message(self):
        checker = make_checker([2, 1, 3])
        checker.check([1, 2, 3])
        checker.check([1, 2, 3])
        self.assertIn("한바퀴 끝! 처음으로!!", checker.view.messages)
        self.assertEqual(checker.board.lcd_lines[0], "Pos 1 <-> 2")


class SelectionSortTest(unittest.TestCase):
    def test_steps(self):
        steps = selection_sort([5, 2, 8, 1])
        self.assertEqual([(s.a, s.b, s.swap) for s in steps], [(0, 3, True), (1, 1, False), (2, 3, True)])

    def test_lcd_does_not_reveal_where_the_smallest_card_is(self):
        checker = make_checker([5, 2, 8, 1], "selection")
        self.assertEqual(checker.board.lcd_lines, ["Select pos 1", "min of 1-4"])

    def test_correct_swap_then_already_in_place(self):
        checker = make_checker([5, 2, 8, 1], "selection")
        checker.check([1, 2, 8, 5])
        self.assertIn("1번째 자리 완성!", checker.view.messages)
        self.assertEqual(checker.board.lcd_lines, ["Select pos 2", "min of 2-4"])
        checker.check([1, 2, 8, 5])  # 2 는 이미 제자리
        self.assertIn("통과! 안 바꿔도 돼요!", checker.view.messages)
        self.assertEqual(checker.wrongs, 0)

    def test_left_alone_when_a_smaller_card_exists(self):
        checker = make_checker([5, 2, 8, 1], "selection")
        checker.check([5, 2, 8, 1])
        self.assertIn("더 작은 카드가 있어요!", checker.view.messages)
        self.assertEqual(checker.wrongs, 1)

    def test_swapped_with_a_card_that_is_not_the_smallest(self):
        checker = make_checker([5, 2, 8, 1], "selection")
        checker.check([2, 5, 8, 1])
        self.assertIn("틀렸어요", checker.view.messages)
        self.assertEqual(checker.prev, [5, 2, 8, 1])

    def test_fits_on_the_lcd(self):
        for step in selection_sort(list(range(16, 0, -1))):
            self.assertTrue(all(len(line) <= 16 for line in step.lcd))


class RegisterTest(unittest.TestCase):
    def test_register_retries_until_all_cards_seen(self):
        checker = SortChecker(FakeView(), FakeBoard(), queue.Queue(), threading.Event(),
                              SORTS, sort="bubble", num_cards=3)
        checker._sleep = lambda secs: None
        reads = iter([[("3", 0), ("1", 10)], [("3", 0), ("1", 10), ("2", 20)]])
        checker.view.read_text = lambda expected: next(reads)
        checker.wait_trigger = lambda: None
        checker.register_cards()
        self.assertEqual(checker.card_list, [3, 1, 2])
        self.assertEqual(checker.board.lcd_lines, ["Pos 1 <-> 2", "3 ? 1"])

    def test_confirm_by_space_or_voice(self):
        checker = make_checker([2, 1])
        checker.triggers.get_nowait = self._raise_empty
        for event in [("key", " "), ("word", "확인")]:
            checker.triggers.put(event)
            checker.wait_trigger()

    @staticmethod
    def _raise_empty():
        raise queue.Empty

    def test_stop(self):
        checker = make_checker([2, 1])
        checker.stop_event.set()
        with self.assertRaises(Stopped):
            checker.wait_trigger()


class ChooseSortTest(unittest.TestCase):
    def make(self):
        checker = SortChecker(FakeView(), FakeBoard(), queue.Queue(), threading.Event(), SORTS)
        checker._sleep = lambda secs: None
        return checker

    def choose(self, checker, events):
        """wait_for 가 큐를 비우기 전에 넣은 신호가 사라지지 않도록, 신호를 차례로 흘려보낸다."""
        events = iter(events)
        checker.wait_for = lambda accept: next(r for r in map(accept, events) if r is not None)
        checker.choose_sort()

    def test_choose_by_number_key(self):
        checker = self.make()
        self.choose(checker, [("key", " "), ("key", "9"), ("key", "1")])
        self.assertIs(checker.method, SORTS["bubble"])
        self.assertEqual(checker.board.lcd_lines[0], "Choose sort")

    def test_choose_by_voice(self):
        checker = self.make()
        self.choose(checker, [("word", "확인"), ("word", "버블")])
        self.assertIs(checker.method, SORTS["bubble"])
        self.assertIn("버블 정렬을 시작해요!", checker.view.messages)

    def test_choose_by_saying_number(self):
        checker = self.make()
        self.choose(checker, [("word", "확인"), ("word", "1번")])
        self.assertIs(checker.method, SORTS["bubble"])

    def test_choose_selection_by_key_or_voice(self):
        for event in [("key", "2"), ("word", "선택"), ("word", "2번")]:
            checker = self.make()
            self.choose(checker, [event])
            self.assertIs(checker.method, SORTS["selection"], event)

    def test_preset_sort_skips_question(self):
        checker = make_checker([2, 1])
        checker.choose_sort()
        self.assertFalse(any("골라주세요" in m for m in checker.view.messages))


if __name__ == "__main__":
    unittest.main()
