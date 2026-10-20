"""음성 인식: 정해 둔 말('확인', 정렬 이름 등)을 알아들으면 알려준다.

인터넷 없이 동작하는 Vosk 한국어 모델을 사용한다.
모델이나 마이크가 없으면 음성 인식 없이 실행한다.
"""
import json
import os
import queue
import threading

SAMPLE_RATE = 16000


class KeywordListener(threading.Thread):
    def __init__(self, model_path, words, triggers, stop_event):
        super().__init__(daemon=True)
        self.model_path = model_path
        self.words = sorted(set(words), key=len, reverse=True)  # 긴 말부터 찾는다
        self.triggers = triggers
        self.stop_event = stop_event

    def run(self):
        if not os.path.isdir(self.model_path):
            print(f"[음성] 모델 폴더가 없어 음성 인식 없이 실행합니다: {self.model_path}")
            return
        try:
            import sounddevice as sd
            import vosk
        except ImportError as e:
            print(f"[음성] 라이브러리가 없어 음성 인식 없이 실행합니다 ({e})")
            return

        vosk.SetLogLevel(-1)
        model = vosk.Model(self.model_path)
        # 인식할 말을 좁혀서 잘못 알아듣는 것을 줄인다
        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE,
                                          json.dumps(self.words + ["[unk]"], ensure_ascii=False))
        audio = queue.Queue()

        def on_audio(data, frames, time, status):
            audio.put(bytes(data))

        try:
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16",
                                   channels=1, callback=on_audio):
                print(f"[음성] 알아듣는 말: {', '.join(self.words)}")
                while not self.stop_event.is_set():
                    try:
                        data = audio.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        text = json.loads(recognizer.Result())["text"]
                    else:
                        text = json.loads(recognizer.PartialResult())["partial"]
                    text = text.replace(" ", "")
                    for word in self.words:
                        if word in text:
                            self.triggers.put(("word", word))
                            recognizer.Reset()
                            break
        except Exception as e:
            print(f"[음성] 마이크를 사용할 수 없어 음성 인식을 끕니다 ({e})")
