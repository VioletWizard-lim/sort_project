# 카드 정렬 확인 프로그램 (Python)

학생이 숫자 카드를 직접 옮기며 정렬할 때, 카메라로 카드를 읽어
**한 단계씩 맞게 했는지 확인**해 주는 프로그램입니다.
Scratch 프로젝트 `35(final)` (`scratch/35final.sb3`)를 Python으로 옮겼습니다.

지금 들어 있는 정렬 방법은 **버블 정렬**(`bubble`)입니다.

- 카메라 창에 실시간 영상, 인식한 숫자, 말풍선, LCD/LED 상태가 표시됩니다.
- 카드를 옮긴 뒤 **스페이스바**를 누르거나 **"확인"**이라고 말하면 카드를 읽습니다.
- 아두이노의 RGB LED(9·10·11번 핀)와 I2C LCD(16x2)로 결과를 보여줍니다.
  - 파랑: 정답 / 통과, 빨강: 틀림, 노랑 깜빡임: 카드가 다 안 보임, 무지개: 정렬 완료
  - LCD에는 지금 비교할 위치와 카드(`Pos 1 <-> 2`, `5 ? 2`)가 나옵니다.
- `q`나 `ESC`를 누르거나 창을 닫으면 끝납니다.

## 설치

```bash
pip install -r requirements.txt
```

### 음성 인식 (선택)
[Vosk 한국어 모델](https://alphacephei.com/vosk/models) `vosk-model-small-ko-0.22`를 받아
`models/vosk-model-small-ko-0.22` 폴더에 압축을 풉니다. 모델이 없으면 스페이스바로만 진행합니다.

### 아두이노 (선택)
1. Arduino IDE에서 **LiquidCrystal I2C** 라이브러리(Frank de Brabander) 설치
2. `arduino/sort_board/sort_board.ino`를 우노에 업로드
3. LCD가 안 나오면 코드에 있는 주소 `0x20`을 `0x27`이나 `0x3F`로 바꿔 보세요.

아두이노가 없어도 카메라 창에 LCD/LED 상태가 나오기 때문에 그대로 실행할 수 있습니다.

## 실행

```bash
python main.py                      # 버블 정렬, 기본 카메라, 아두이노 자동으로 찾기
python main.py --sort bubble        # 정렬 방법 고르기
python main.py --camera 1           # 다른 카메라 쓰기
python main.py --port COM3          # 아두이노 포트 직접 지정 (맥/리눅스: /dev/ttyACM0)
python main.py --port none          # 아두이노 없이 실행
python main.py --cards 6            # 카드 장수 바꾸기 (기본 8장)
python main.py --camera http://192.168.0.10:8080/video   # 휴대폰 카메라 앱(IP Webcam 등)
```

말풍선의 한글이 안 보이면 `--font`로 한글 글꼴 파일을 지정하세요.
(Windows는 맑은 고딕, macOS는 Apple SD 산돌고딕을 자동으로 찾습니다.)

## 정렬 방법 추가하기

`sorts.py`에 함수를 하나 만들고 `SORTS`에 등록하면 됩니다.
함수는 처음 카드 배열을 받아서, 학생이 거쳐야 할 **단계(`Step`) 목록**을 돌려줍니다.

```python
Step(a, b, swap, message=None)
```
- `a`, `b`: 비교할 두 카드의 위치 (0부터 셈)
- `swap`: `True`이면 학생이 두 카드를 바꿔야 정답, `False`이면 그대로 두고 확인해야 정답
- `message`: 그 단계를 통과한 뒤에 보여줄 말풍선 (예: `"한바퀴 끝! 처음으로!!"`)

예를 들어 선택 정렬은 한 바퀴마다 가장 작은 카드를 앞으로 보내는 단계 하나로 만들 수 있습니다.

```python
def selection_sort(cards):
    arr = list(cards)
    steps = []
    for i in range(len(arr) - 1):
        m = min(range(i, len(arr)), key=lambda k: arr[k])
        step = Step(i, m, m != i)
        steps.append(step)
        arr = apply(arr, step)
    return steps


SORTS = {
    "bubble": bubble_sort,
    "selection": selection_sort,
}
```

등록한 뒤 `python main.py --sort selection`으로 실행합니다.
`tests/test_checker.py`는 `SORTS`에 있는 모든 정렬을 자동으로 검사해서,
단계를 끝까지 따라가면 카드가 제대로 정렬되는지 확인합니다.

## 파일 구성

| 파일 | 내용 | Scratch에서 |
|---|---|---|
| `main.py` | 실행, 옵션 처리 | 초록 깃발 |
| `checker.py` | 학생이 옮긴 카드가 지금 단계에 맞는지 확인 | Ani 스프라이트 스크립트 |
| `sorts.py` | 정렬 방법별 단계 만들기 | (Scratch에서는 판정 블록 안에 버블 정렬이 들어 있었음) |
| `camera.py` | 카메라 창, 글자 인식(EasyOCR) | 글자 인식 / 휴대폰 카메라 확장 |
| `speech.py` | "확인" 음성 인식(Vosk) | 음성 인식 확장 |
| `board.py` | 아두이노 시리얼 통신 | 우노 확장 (RGB, LCD) |
| `arduino/sort_board/sort_board.ino` | 아두이노 코드 | |
| `tests/test_checker.py` | 카메라·보드 없이 하는 테스트 | |

## 테스트

```bash
python -m unittest discover tests
```
