# 버블 정렬 카드 게임 (Python)

Scratch 프로젝트 `35(final)` (`scratch/35final.sb3`)를 Python으로 옮긴 버전입니다.
숫자 카드 8장을 카메라 앞에 놓고 버블 정렬 순서대로 카드를 바꾸면,
카메라로 카드를 읽어 맞았는지 알려줍니다.

- 카메라 창에 실시간 영상, 인식한 숫자, 말풍선, LCD/LED 상태가 표시됩니다.
- **스페이스바** 또는 **"확인"** 이라고 말하면 카드를 읽습니다.
- 아두이노의 RGB LED(9·10·11번 핀)와 I2C LCD(16x2)로 결과를 보여줍니다.
  - 파랑: 정답 / 통과, 빨강: 틀림, 노랑 깜빡임: 카드가 다 안 보임, 무지개: 정렬 완료
- `q` 또는 `ESC`, 창 닫기로 종료합니다.

## 설치

```bash
pip install -r requirements.txt
```

### 음성 인식 (선택)
[Vosk 한국어 모델](https://alphacephei.com/vosk/models) `vosk-model-small-ko-0.22` 를 받아
`models/vosk-model-small-ko-0.22` 폴더에 압축을 풉니다. 모델이 없으면 스페이스바로만 진행합니다.

### 아두이노 (선택)
1. Arduino IDE에서 라이브러리 **LiquidCrystal I2C** (Frank de Brabander) 설치
2. `arduino/sort_board/sort_board.ino` 를 우노에 업로드
3. LCD가 안 나오면 코드의 주소 `0x20` 을 `0x27` 또는 `0x3F` 로 바꿔 보세요.

아두이노가 없어도 카메라 창에 LCD/LED 상태가 표시되므로 그대로 실행할 수 있습니다.

## 실행

```bash
python main.py                      # 기본 카메라, 아두이노 자동 찾기
python main.py --camera 1           # 다른 카메라
python main.py --port COM3          # 아두이노 포트 지정 (맥/리눅스: /dev/ttyACM0)
python main.py --port none          # 아두이노 없이
python main.py --camera http://192.168.0.10:8080/video   # 휴대폰 카메라 앱(IP Webcam 등)
```

말풍선 한글이 안 보이면 `--font` 로 한글 글꼴 파일을 지정하세요.
(Windows는 맑은 고딕, macOS는 Apple SD 산돌고딕을 자동으로 찾습니다.)

## 파일 구성

| 파일 | 내용 | Scratch에서 |
|---|---|---|
| `main.py` | 실행, 옵션 처리 | 초록 깃발 |
| `game.py` | 게임 로직 | Ani 스프라이트의 스크립트와 사용자 정의 블록 |
| `camera.py` | 카메라 창, 글자 인식(EasyOCR) | 글자 인식 / 휴대폰 카메라 확장 |
| `speech.py` | "확인" 음성 인식(Vosk) | 음성 인식 확장 |
| `board.py` | 아두이노 시리얼 통신 | 우노 확장 (RGB, LCD) |
| `arduino/sort_board/sort_board.ino` | 아두이노 코드 | |
| `tests/test_game.py` | 카메라·보드 없이 게임 로직 테스트 | |

`game.py` 의 함수는 Scratch 블록 이름과 대응합니다:
`read_cards`(카드 읽기), `register_cards`(처음 카드 등록), `judge`(정답 판정),
`next_compare`(다음 비교), `handle_wrong`(오답처리), `show_guide`(LCD 안내).

## 테스트

```bash
python -m unittest discover tests
```
