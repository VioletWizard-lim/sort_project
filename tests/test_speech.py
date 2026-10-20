"""음성 인식 중 마이크·인터넷 없이 확인할 수 있는 부분 테스트."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speech import BLOCK, VoiceDetector, find_keyword  # noqa: E402

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
        sound = blocks(100, 10) + blocks(100, 5) + blocks(3000, 8) + blocks(100, 10)
        segments = run(VoiceDetector(), sound)
        self.assertEqual(len(segments), 1)
        # 말 직전 0.3초 + 말 0.8초 + 끝난 뒤 조용한 0.6초
        self.assertEqual(len(segments[0]), (3 + 8 + 6) * BLOCK * 2)

    def test_quiet_room_gives_nothing(self):
        self.assertEqual(run(VoiceDetector(), blocks(100, 60)), [])

    def test_short_click_is_ignored(self):
        sound = blocks(100, 10) + blocks(3000, 1) + blocks(100, 10)
        self.assertEqual(run(VoiceDetector(), sound), [])

    def test_long_speech_is_cut(self):
        sound = blocks(100, 10) + blocks(3000, 120)
        self.assertEqual(len(run(VoiceDetector(), sound)), 2)

    def test_two_phrases(self):
        sound = blocks(100, 10) + (blocks(3000, 5) + blocks(100, 8)) * 2
        self.assertEqual(len(run(VoiceDetector(), sound)), 2)


if __name__ == "__main__":
    unittest.main()
