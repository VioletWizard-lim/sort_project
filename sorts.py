"""정렬 방법별로 학생이 따라야 할 단계를 만든다.

각 정렬 함수는 카드 리스트를 받아 Step 리스트를 돌려준다.
Step 하나는 '카드 두 장(a, b)을 비교해서 바꿀지 말지'이다.
    swap=True  -> 학생이 두 카드를 바꿔야 정답
    swap=False -> 학생이 그대로 두고 확인해야 정답
message 가 있으면 그 단계를 통과한 뒤에 말풍선으로 보여준다.

새 정렬을 추가하려면 같은 모양의 함수를 만들고 SORTS 에 이름을 등록하면 된다.
"""
from dataclasses import dataclass


@dataclass
class Step:
    a: int
    b: int
    swap: bool
    message: str = None


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


SORTS = {
    "bubble": bubble_sort,
}
