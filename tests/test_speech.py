"""음성 결과에서 정해 둔 말을 찾는 부분 테스트 (마이크, 모델 없이)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speech import find_keyword  # noqa: E402

WORDS = ["확인", "버블", "거품"]


def result(*pairs):
    return {"text": " ".join(w for w, _ in pairs),
            "result": [{"word": w, "conf": c} for w, c in pairs]}


class FindKeywordTest(unittest.TestCase):
    def test_finds_word(self):
        self.assertEqual(find_keyword(result(("확인", 0.95)), WORDS), "확인")

    def test_word_inside_longer_word(self):
        self.assertEqual(find_keyword(result(("네", 0.9), ("확인했어요", 0.9)), WORDS), "확인")

    def test_other_speech_is_ignored(self):
        self.assertIsNone(find_keyword(result(("안녕하세요", 0.98), ("선생님", 0.9)), WORDS))

    def test_unsure_word_is_ignored(self):
        self.assertIsNone(find_keyword(result(("확인", 0.4)), WORDS))

    def test_empty_result(self):
        self.assertIsNone(find_keyword({"text": ""}, WORDS))


if __name__ == "__main__":
    unittest.main()
