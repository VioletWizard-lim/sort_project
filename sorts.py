"""정렬 방법별로 학생이 따라야 할 단계를 만든다.

각 정렬 함수는 카드 리스트를 받아 Step 리스트를 돌려준다.
Step 하나는 '카드 두 장(a, b)을 비교해서 바꿀지 말지'이다.
    swap=True  -> 학생이 두 카드를 바꿔야 정답
    swap=False -> 학생이 그대로 두고 확인해야 정답
message 가 있으면 그 단계를 통과한 뒤에 말풍선으로 보여준다.
lcd 를 주면 LCD 안내를 그 두 줄로 바꾼다. (기본은 'Pos a <-> b' 와 두 카드. 선택 정렬처럼
바꿀 위치를 알려 주면 정답이 드러나는 정렬에서 쓴다)
hint 는 바꿔야 하는데 그대로 뒀을 때 할 말이다. (기본: '바꿔야 돼요!')

새 정렬을 추가하려면 같은 모양의 함수를 만들고 SORTS 에 SortMethod 로 등록하면 된다.
SORTS 에 넣은 순서대로 키보드 숫자 1, 2, 3 ... 이 붙는다.
"""
from dataclasses import dataclass


@dataclass
class Step:
    a: int
    b: int
    swap: bool
    message: str = None
    lcd: tuple = None
    hint: str = None


@dataclass
class SortMethod:
    name: str          # 말풍선에 보여줄 이름
    lcd_name: str      # LCD에 보여줄 영어 이름 (LCD는 한글을 못 쓴다)
    words: tuple       # 말로 고를 때 알아들을 말
    make_steps: object  # 카드 리스트 -> Step 리스트


def apply(cards, step):
    """단계대로 했을 때의 카드 배열"""
    result = list(cards)
    if step.swap:
        result[step.a], result[step.b] = result[step.b], result[step.a]
    return result


def bubble_sort(cards):
    """버블 정렬: 옆 카드끼리 비교하며 큰 카드를 오른쪽 끝으로 보낸다.
    한 바퀴 동안 한 번도 안 바꿨으면 거기서 끝난다."""
    arr = list(cards)
    steps = []
    end = len(arr) - 1
    while end > 0:
        swaps = 0
        for j in range(end):
            step = Step(j, j + 1, arr[j] > arr[j + 1])
            steps.append(step)
            arr = apply(arr, step)
            swaps += step.swap
        end -= 1
        if swaps == 0 or end == 0:
            break
        steps[-1].message = "한바퀴 끝! 처음으로!!"
    return steps


def selection_sort(cards):
    """선택 정렬: 앞자리부터 차례로, 남은 카드 중 가장 작은 카드를 찾아 그 자리로 가져온다.
    가장 작은 카드는 학생이 직접 찾아야 하므로 LCD 에 그 위치를 보여 주지 않는다."""
    arr = list(cards)
    n = len(arr)
    steps = []
    for i in range(n - 1):
        smallest = min(range(i, n), key=lambda k: arr[k])
        step = Step(i, smallest, smallest != i,
                    message=f"{i + 1}번째 자리 완성!",
                    lcd=(f"Select pos {i + 1}", f"min of {i + 1}-{n}"),
                    hint="더 작은 카드가 있어요!")
        steps.append(step)
        arr = apply(arr, step)
    return steps


def insertion_sort(cards):
    """삽입 정렬: 두 번째 카드부터 차례로, 왼쪽 카드와 한 칸씩 바꾸며 제자리까지 옮긴다.
    왼쪽 카드가 더 작거나 같아지면(바꾸지 않고 확인) 또는 맨 앞에 닿으면 그 카드는 끝이다."""
    arr = list(cards)
    steps = []
    for i in range(1, len(arr)):
        j = i
        while j > 0:
            step = Step(j - 1, j, arr[j - 1] > arr[j])
            steps.append(step)
            arr = apply(arr, step)
            if not step.swap:
                break
            j -= 1
        steps[-1].message = f"앞의 {i + 1}장 정렬 완료!"
    return steps


SORTS = {
    "bubble": SortMethod("버블 정렬", "Bubble", ("버블", "거품", "bubble"), bubble_sort),
    "selection": SortMethod("선택 정렬", "Select", ("선택", "selection"), selection_sort),
    "insertion": SortMethod("삽입 정렬", "Insert", ("삽입", "insertion"), insertion_sort),
}
