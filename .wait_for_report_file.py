#!/usr/bin/env python3
import os.path
import time

TIME_TO_WAIT = 10
TIME_COUNTER = 0
FILE_PATH = "./test-results/cucumber.json"

while not os.path.exists(FILE_PATH):
    time.sleep(1)
    TIME_COUNTER += 1
    if TIME_COUNTER == TIME_TO_WAIT:
        break

if TIME_COUNTER != TIME_TO_WAIT:
    if os.path.isfile(FILE_PATH):
        print("The file exists!")
        return 0
    else:
        print(f"{FILE_PATH} isn't a file!")
        return -1
else:
    print(f"The file did not appear in {TIME_TO_WAIT} seconds")
    return -2
