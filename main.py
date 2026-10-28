"""카드 정렬 확인 프로그램 실행 파일.

    python main.py                     # 시작할 때 정렬 방법을 고른다
    python main.py --sort bubble --camera 1 --port COM3
    python main.py --camera http://192.168.0.10:8080/video   # 휴대폰 카메라 앱
"""
import argparse
import queue
import threading
import traceback

from board import Board
from camera import CameraView, CardReader
from checker import CONFIRM_WORD, NUM_CARDS, SortChecker, number_words
from sorts import SORTS
from speech import KeywordListener


def parse_args():
    parser = argparse.ArgumentParser(description="카드 정렬 확인 프로그램")
    parser.add_argument("--sort", choices=list(SORTS), default=None,
                        help="정렬 방법을 미리 정하기 (안 정하면 시작할 때 말이나 숫자키로 고른다)")
    parser.add_argument("--camera", default="0",
                        help="카메라 번호 또는 영상 주소 (기본: 0)")
    parser.add_argument("--port", default="auto",
                        help="아두이노 포트 (auto / COM3 / /dev/ttyACM0 / none)")
    parser.add_argument("--cards", type=int, default=NUM_CARDS,
                        help=f"카드 장수 (기본: {NUM_CARDS})")
    parser.add_argument("--font", default=None, help="말풍선에 쓸 한글 글꼴 파일")
    parser.add_argument("--gpu", action="store_true", help="OCR에 GPU 사용")
    return parser.parse_args()


def main():
    args = parse_args()
    source = int(args.camera) if args.camera.isdigit() else args.camera

    stop_event = threading.Event()
    triggers = queue.Queue()

    board = Board(args.port)
    reader = CardReader(gpu=args.gpu)
    view = CameraView(source, reader, board, triggers, stop_event, font_path=args.font)
    checker = SortChecker(view, board, triggers, stop_event, SORTS,
                          sort=args.sort, num_cards=args.cards)

    words = [CONFIRM_WORD] + [word for method in SORTS.values() for word in method.words]
    words += [word for number in range(1, len(SORTS) + 1) for word in number_words(number)]
    listener = KeywordListener(words, triggers, stop_event)
    view.listener = listener
    listener.start()

    def run_checker():
        try:
            checker.run()
        except Exception:
            traceback.print_exc()
            stop_event.set()

    checker_thread = threading.Thread(target=run_checker, daemon=True)
    checker_thread.start()

    try:
        view.run()  # 카메라 창은 메인 스레드에서 띄운다
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        checker_thread.join(timeout=2)
        board.close()


if __name__ == "__main__":
    main()
