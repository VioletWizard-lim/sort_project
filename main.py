"""카드 정렬 확인 프로그램 실행 파일.

    python main.py
    python main.py --sort bubble --camera 1 --port COM3
    python main.py --camera http://192.168.0.10:8080/video   # 휴대폰 카메라 앱
"""
import argparse
import queue
import threading
import traceback

from board import Board
from camera import CameraView, CardReader
from checker import NUM_CARDS, SortChecker
from sorts import SORTS
from speech import KeywordListener


def parse_args():
    parser = argparse.ArgumentParser(description="카드 정렬 확인 프로그램")
    parser.add_argument("--sort", choices=sorted(SORTS), default="bubble",
                        help="정렬 방법 (기본: bubble)")
    parser.add_argument("--camera", default="0",
                        help="카메라 번호 또는 영상 주소 (기본: 0)")
    parser.add_argument("--port", default="auto",
                        help="아두이노 포트 (auto / COM3 / /dev/ttyACM0 / none)")
    parser.add_argument("--cards", type=int, default=NUM_CARDS,
                        help=f"카드 장수 (기본: {NUM_CARDS})")
    parser.add_argument("--vosk-model", default="models/vosk-model-small-ko-0.22",
                        help="Vosk 한국어 음성 모델 폴더")
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
    checker = SortChecker(view, board, triggers, stop_event, SORTS[args.sort], num_cards=args.cards)

    KeywordListener(args.vosk_model, "확인", triggers, stop_event).start()

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
