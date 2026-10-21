"""음성 인식 중 마이크·인터넷 없이 확인할 수 있는 부분 테스트."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speech import BLOCK, VoiceDetector, amplify, find_keyword  # noqa: E402

WORDS = ["확인", "버블", "거품"]


def blocks(level, count):
    """level 크기의 소리 블록 count 개 (사인파)"""
    t = np.arange(BLOCK)
    wave = (np.sin(t / 5) * level * np.sqrt(2)).astype(np.int16)
    return [wave.copy() for _ in range(count)]


def run(detector, sound):
    return [seg for seg in map(detector.feed, sound) if seg is not None]


class FindKeywordTest(unittest.TestCase):
    def test_finds_word(self):
        self.assertEqual(find_keyword("확인", WORDS), "확인")
        self.assertEqual(find_keyword("네 확인했어요", WORDS), "확인")
        self.assertEqual(find_keyword("버블 정렬", WORDS), "버블")

    def test_other_speech_is_ignored(self):
        self.assertIsNone(find_keyword("안녕하세요 선생님", WORDS))
        self.assertIsNone(find_keyword("", WORDS))


class VoiceDetectorTest(unittest.TestCase):
    def test_cuts_one_phrase(self):
        sound = blocks(100, 15) + blocks(3000, 8) + blocks(100, 10)
        segments = run(VoiceDetector(), sound)
        self.assertEqual(len(segments), 1)
        # 말 직전 0.3초 + 말 0.8초 + 끝난 뒤 조용한 0.6초
        self.assertEqual(len(segments[0]), (3 + 8 + 6) * BLOCK * 2)

    def test_quiet_room_gives_nothing(self):
        self.assertEqual(run(VoiceDetector(), blocks(100, 60)), [])

    def test_short_click_is_ignored(self):
        sound = blocks(100, 10) + blocks(3000, 1) + blocks(100, 10)
        self.assertEqual(run(VoiceDetector(), sound), [])

    def test_long_sound_is_cut_then_treated_as_noise(self):
        """끝없이 이어지는 큰 소리는 늦어도 5초에서 자르고, 그 뒤로는 소음(선풍기 등)으로 본다."""
        sound = blocks(100, 10) + blocks(3000, 120)
        segments = run(VoiceDetector(), sound)
        self.assertEqual(len(segments), 1)
        self.assertLessEqual(len(segments[0]), 50 * BLOCK * 2)

    def test_two_phrases(self):
        sound = blocks(100, 10) + (blocks(3000, 5) + blocks(100, 8)) * 2
        self.assertEqual(len(run(VoiceDetector(), sound)), 2)

    def test_quiet_laptop_mic(self):
        """노트북 내장 마이크처럼 말소리가 작게(150) 들어와도 소음(30)보다 크면 잡는다."""
        sound = blocks(30, 10) + blocks(150, 6) + blocks(30, 10)
        self.assertEqual(len(run(VoiceDetector(), sound)), 1)

    def test_speaking_right_at_start(self):
        """마이크가 켜지자마자 말해도 소음 기준이 올라가 버리지 않아서 다음 말은 잡는다."""
        sound = blocks(3000, 8) + blocks(100, 10) + blocks(3000, 6) + blocks(100, 10)
        self.assertEqual(len(run(VoiceDetector(), sound)), 1)


class AmplifyTest(unittest.TestCase):
    def test_quiet_speech_is_made_louder(self):
        quiet = np.array([0, 1000, -2000, 500], dtype=np.int16)
        self.assertEqual(int(np.max(np.abs(amplify(quiet)))), 20000)

    def test_loud_speech_is_unchanged(self):
        loud = np.array([0, 30000, -25000], dtype=np.int16)
        self.assertTrue(np.array_equal(amplify(loud), loud))

    def test_gain_is_limited(self):
        tiny = np.array([0, 10, -10], dtype=np.int16)
        self.assertEqual(int(np.max(np.abs(amplify(tiny)))), 100)


if __name__ == "__main__":
    unittest.main()
