"""카메라와 아두이노 없이 게임 로직을 확인하는 테스트.

    python -m unittest discover tests
"""
import os
import queue
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import BLUE, RED, GameStopped, SortGame, parse_card  # noqa: E402


class FakeView:
    def __init__(self):
        self.messages = []

    def say(self, message):
        if message:
            self.messages.append(message)

    def read_text(self):
        return []


class FakeBoard:
    def __init__(self):
        self.leds = []
        self.lcd_lines = ["", ""]

    def rgb(self, color):
        self.leds.append(tuple(color))

    def lcd(self, row0="", row1=""):
        self.lcd_lines = [row0, row1]


def make_game(cards):
    game = SortGame(FakeView(), FakeBoard(), queue.Queue(), threading.Event(), num_cards=len(cards))
    game._sleep = lambda secs: None
    game.card_list = list(cards)
    game.prev = list(cards)
    game.end = len(cards) - 1
    return game


def no_rainbow(game):
    def stop():
        game.done = True
    game.celebrate = stop


class ParseCardTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_card("1 2"), 12)
        self.assertEqual(parse_card("7"), 7)
        self.assertIsNone(parse_card("가"))
        self.assertIsNone(parse_card(""))


class ReadCardsTest(unittest.TestCase):
    def test_sorted_by_x_and_filtered(self):
        game = make_game([3, 1, 2])
        game.view.read_text = lambda: [("2", 300), ("9", 50), ("3", 10), ("1", 200), ("abc", 5)]
        self.assertEqual(game.read_cards(), [3, 1, 2])


class StepTest(unittest.TestCase):
    def test_correct_swap(self):
        game = make_game([3, 1, 2])
        game.step([1, 3, 2])
        self.assertEqual(game.prev, [1, 3, 2])
        self.assertEqual(game.pos, 1)
        self.assertEqual(game.swaps, 1)
        self.assertIn(BLUE, game.board.leds)

    def test_swap_not_needed(self):
        game = make_game([1, 3, 2])
        game.step([3, 1, 2])
        self.assertEqual(game.wrongs, 1)
        self.assertEqual(game.pos, 0)
        self.assertIn(RED, game.board.leds)

    def test_pass_without_swap(self):
        game = make_game([1, 3, 2])
        game.step([1, 3, 2])
        self.assertEqual(game.pos, 1)
        self.assertEqual(game.wrongs, 0)

    def test_should_have_swapped(self):
        game = make_game([3, 1, 2])
        game.step([3, 1, 2])
        self.assertEqual(game.wrongs, 1)
        self.assertEqual(game.board.lcd_lines[0], "Pos 1 <-> 2")

    def test_other_cards_moved(self):
        game = make_game([3, 1, 2, 4])
        game.step([1, 3, 4, 2])
        self.assertEqual(game.wrongs, 1)
        self.assertEqual(game.prev, [3, 1, 2, 4])

    def test_missing_card(self):
        game = make_game([3, 1, 2])
        game.step([3, 1])
        self.assertEqual(game.pos, 0)
        self.assertEqual(game.view.messages, ["카드가 제대로 안보여요!"])

    def test_full_sort(self):
        cards = [5, 2, 8, 1, 7, 3, 6, 4]
        game = make_game(cards)
        no_rainbow(game)
        arr = list(cards)
        while not game.done:
            p = game.pos
            if arr[p] > arr[p + 1]:
                arr[p], arr[p + 1] = arr[p + 1], arr[p]
            game.step(list(arr))
        self.assertEqual(arr, sorted(cards))
        self.assertEqual(game.wrongs, 0)

    def test_already_sorted_ends_after_one_pass(self):
        game = make_game([1, 2, 3, 4])
        no_rainbow(game)
        for _ in range(3):
            game.step([1, 2, 3, 4])
        self.assertTrue(game.done)
        self.assertEqual(game.compares, 3)


class RegisterTest(unittest.TestCase):
    def test_register_retries_until_all_cards_seen(self):
        game = SortGame(FakeView(), FakeBoard(), queue.Queue(), threading.Event(), num_cards=3)
        game._sleep = lambda secs: None
        reads = iter([[("3", 0), ("1", 10)], [("3", 0), ("1", 10), ("2", 20)]])
        game.view.read_text = lambda: next(reads)
        game.triggers.put("space")
        game.wait_trigger = lambda: None
        game.register_cards()
        self.assertEqual(game.card_list, [3, 1, 2])
        self.assertEqual(game.board.lcd_lines, ["Pos 1 <-> 2", "3 ? 1"])

    def test_stop(self):
        game = make_game([1, 2])
        game.stop_event.set()
        with self.assertRaises(GameStopped):
            game.wait_trigger()


if __name__ == "__main__":
    unittest.main()
