from heapq import heappop, heappush
from itertools import count
from queue import PriorityQueue

test = []
counter = count()

priority_queue = PriorityQueue()
priority_queue.put((5, "first_input"))
priority_queue.put((3, "second_input"))
priority_queue.put((0, "third_input"))
priority_queue.put((1, "fourth_input"))
priority_queue.put((1, "fifth_input"))
priority_queue.put((1, "sixth_input"))

# heappush(test, (5, next(counter), "first_input"))
# heappush(test, (3, next(counter), "second_input"))
# heappush(test, (0, next(counter), "third_input"))
# heappush(test, (1, next(counter), "fourth_input"))
# heappush(test, (1, next(counter), "fifth_input"))
# heappush(test, (1, next(counter), "sixth_input"))
# heappush(test, (1, next(counter), "seventh_input"))

# while test:
#     print(heappop(test))

while not priority_queue.empty():
    print(priority_queue.get())
