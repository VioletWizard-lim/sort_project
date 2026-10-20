"""음성 인식: 정해 둔 말('확인', 정렬 이름 등)을 알아들으면 알려준다.

인터넷 없이 동작하는 Vosk 한국어 모델을 사용한다.
모델이 없으면 처음 한 번 인터넷에서 받아 온다. (main.py 가 프로그램을 켜기 전에 ensure_model 을 부른다)
모델이나 마이크가 없으면 음성 인식 없이 실행한다.
"""
import json
import os
import queue
import threading
import urllib.request
import zipfile

SAMPLE_RATE = 16000
MIN_CONFIDENCE = 0.7  # 이보다 자신 없게 알아들은 말은 무시한다
MODEL_BASE_URL = "https://alphacephei.com/vosk/models/"


def ensure_model(model_path):
    """모델 폴더가 없으면 받아서 압축을 푼다. 성공하면 True."""
    if os.path.isdir(model_path):
        return True
    name = os.path.basename(os.path.normpath(model_path))
    parent = os.path.dirname(os.path.abspath(model_path))
    zip_path = os.path.join(parent, name + ".zip")
    print("[음성] 음성 인식 모델을 받는 중... (처음 한 번, 약 80MB)")
    try:
        os.makedirs(parent, exist_ok=True)
        urllib.request.urlretrieve(MODEL_BASE_URL + name + ".zip", zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(parent)
    except Exception as e:
        print(f"[음성] 모델을 받지 못했습니다 ({e})")
        return False
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    print("[음성] 모델 준비 완료")
    return os.path.isdir(model_path)


def find_keyword(result, words, min_confidence=MIN_CONFIDENCE):
    """Vosk 최종 결과에서 정해 둔 말을 찾는다. 없으면 None.
    result 는 SetWords(True) 로 받은 {"text": ..., "result": [{"word", "conf"}, ...]}."""
    for heard in result.get("result", []):
        if heard["conf"] < min_confidence:
            continue
        for word in words:
            if word in heard["word"]:
                return word
    return None


class KeywordListener(threading.Thread):
    def __init__(self, model_path, words, triggers, stop_event):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.words = sorted(set(words), key=len, reverse=True)  # 긴 말부터 찾는다
        self.triggers = triggers
        self.stop_event = stop_event

    def run(self):
        try:
            import sounddevice as sd
            import vosk
        except ImportError as e:
            print(f"[음성] 라이브러리가 없어 음성 인식 없이 실행합니다 ({e})")
            return
        if not os.path.isdir(self.model_path):
            print(f"[음성] 모델이 없어 음성 인식 없이 실행합니다: {self.model_path}")
            return

        vosk.SetLogLevel(-1)
        model = vosk.Model(self.model_path)
        # 단어 목록으로 좁히면 아무 소리나 그 단어로 끼워 맞추므로, 들은 말을 그대로 받아 적는다
        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)  # 단어마다 얼마나 확실한지(conf)도 받는다
        audio = queue.Queue()

        def on_audio(data, frames, time, status):
            audio.put(bytes(data))

        try:
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16",
                                   channels=1, callback=on_audio):
                print(f"[음성] 마이크: {sd.query_devices(kind='input')['name']}")
                print(f"[음성] 알아듣는 말: {', '.join(self.words)}")
                while not self.stop_event.is_set():
                    try:
                        data = audio.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    # 말이 끝났을 때의 최종 결과만 쓴다 (중간 결과는 자주 바뀐다)
                    if not recognizer.AcceptWaveform(data):
                        continue
                    result = json.loads(recognizer.Result())
                    if not result.get("text"):
                        continue
                    heard = " ".join(f"{w['word']}({w['conf']:.2f})" for w in result.get("result", []))
                    print(f"[음성] 들은 말: {heard}")
                    word = find_keyword(result, self.words)
                    if word:
                        self.triggers.put(("word", word))
        except Exception as e:
            print(f"[음성] 마이크를 사용할 수 없어 음성 인식을 끕니다 ({e})")
