"""음성 인식: 정해 둔 말('확인', 정렬 이름 등)을 알아들으면 알려준다.

Scratch의 음성 인식 확장처럼 구글 음성 인식을 사용한다. (인터넷 필요)
마이크 소리 크기로 말하는 구간을 잘라 구글에 보내고, 받아 적은 글에서 정해 둔 말을 찾는다.
마이크나 인터넷이 없으면 음성 인식 없이 실행한다.
"""
import collections
import queue
import threading

import numpy as np

SAMPLE_RATE = 16000
BLOCK = SAMPLE_RATE // 10   # 0.1초씩 소리를 받는다
LANGUAGE = "ko-KR"


def find_keyword(text, words):
    """받아 적은 글에서 정해 둔 말을 찾는다. 없으면 None."""
    text = text.replace(" ", "")
    for word in words:
        if word in text:
            return word
    return None


class VoiceDetector:
    """소리 크기로 말이 시작하고 끝나는 구간을 잘라 낸다.

    주변 소음은 최근 3초 중 조용했던 순간(하위 20%)의 크기로 잰다.
    그래서 프로그램을 켜자마자 말을 해도 소음 기준이 올라가지 않는다.
    소음보다 충분히 큰 소리가 나면 말이 시작된 것으로 본다.
    """

    def __init__(self, start_ratio=2.5, min_level=60, history_blocks=30, warmup_blocks=5,
                 preroll_blocks=3, silence_blocks=6, min_voiced_blocks=2, max_blocks=50):
        self.start_ratio = start_ratio            # 소음의 몇 배 이상이면 말소리로 볼지
        self.min_level = min_level                # 아주 조용한 곳에서도 이 크기는 넘어야 말소리
        self.history = collections.deque(maxlen=history_blocks)  # 최근 3초 소리 크기
        self.warmup_blocks = warmup_blocks        # 처음 0.5초는 소음만 잰다
        self.preroll_blocks = preroll_blocks      # 말 시작 직전 소리도 붙여서 보낸다
        self.silence_blocks = silence_blocks      # 이만큼(0.6초) 조용하면 말이 끝난 것
        self.min_voiced_blocks = min_voiced_blocks  # 너무 짧은 소리(딸깍 등)는 버린다
        self.max_blocks = max_blocks              # 아무리 길어도 5초에서 자른다

        self.level = 0.0       # 지금 소리 크기 (화면 표시용)
        self.threshold = float(min_level)  # 지금 말소리 기준 (화면 표시용)
        self.preroll = []
        self.buffer = []
        self.voiced = 0
        self.silent = 0

    @property
    def hearing(self):
        """지금 말소리 구간을 모으는 중인지"""
        return bool(self.buffer)

    def feed(self, block):
        """0.1초 소리를 넣는다. 말 한 구간이 끝나면 그 소리(bytes)를, 아니면 None을 돌려준다."""
        self.level = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        self.history.append(self.level)
        if len(self.history) < self.warmup_blocks:
            return None
        noise = float(np.percentile(self.history, 20))
        self.threshold = max(noise * self.start_ratio, self.min_level)
        loud = self.level > self.threshold

        if not self.buffer:
            if not loud:
                self.preroll = (self.preroll + [block])[-self.preroll_blocks:]
                return None
            self.buffer = self.preroll + [block]
            self.preroll = []
            self.voiced, self.silent = 1, 0
            return None

        self.buffer.append(block)
        if loud:
            self.voiced += 1
            self.silent = 0
        else:
            self.silent += 1
        if self.silent < self.silence_blocks and len(self.buffer) < self.max_blocks:
            return None

        segment, voiced = self.buffer, self.voiced
        self.buffer = []
        if voiced < self.min_voiced_blocks:
            return None
        return amplify(np.concatenate(segment)).tobytes()


def amplify(samples, target_peak=20000, max_gain=10.0):
    """작게 녹음된 말소리를 키운다. (노트북 내장 마이크는 소리가 작게 들어오는 경우가 많다)"""
    peak = int(np.max(np.abs(samples.astype(np.int32)))) or 1
    gain = min(max_gain, target_peak / peak)
    if gain <= 1:
        return samples.astype(np.int16)
    return np.clip(samples.astype(np.float64) * gain, -32768, 32767).astype(np.int16)


class KeywordListener(threading.Thread):
    def __init__(self, words, triggers, stop_event):
        super().__init__(daemon=True)
        self.words = sorted(set(words), key=len, reverse=True)  # 긴 말부터 찾는다
        self.triggers = triggers
        self.stop_event = stop_event
        self.detector = VoiceDetector()  # 카메라 창이 마이크 소리 크기를 그릴 때 읽는다
        self.active = False              # 마이크가 켜져 있는지

    def run(self):
        try:
            import sounddevice as sd
            import speech_recognition as sr
        except ImportError as e:
            print(f"[음성] 라이브러리가 없어 음성 인식 없이 실행합니다 ({e})")
            return

        recognizer = sr.Recognizer()
        audio = queue.Queue()

        def on_audio(data, frames, time, status):
            audio.put(data[:, 0].copy())

        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, dtype="int16",
                                channels=1, callback=on_audio):
                print(f"[음성] 마이크: {sd.query_devices(kind='input')['name']}")
                print(f"[음성] 알아듣는 말: {', '.join(self.words)}")
                self.active = True
                while not self.stop_event.is_set():
                    try:
                        segment = self.detector.feed(audio.get(timeout=0.5))
                    except queue.Empty:
                        continue
                    if segment is not None:
                        self._recognize(recognizer, sr, segment)
        except Exception as e:
            print(f"[음성] 마이크를 사용할 수 없어 음성 인식을 끕니다 ({e})")
        finally:
            self.active = False

    def _recognize(self, recognizer, sr, segment):
        try:
            text = recognizer.recognize_google(sr.AudioData(segment, SAMPLE_RATE, 2),
                                               language=LANGUAGE)
        except sr.UnknownValueError:
            print("[음성] 소리는 들었지만 무슨 말인지 알아듣지 못했어요.")
            return
        except sr.RequestError as e:
            print(f"[음성] 구글 음성 인식에 연결하지 못했습니다. 인터넷을 확인하세요 ({e})")
            return
        print(f"[음성] 들은 말: {text}")
        word = find_keyword(text, self.words)
        if word:
            self.triggers.put(("word", word))
