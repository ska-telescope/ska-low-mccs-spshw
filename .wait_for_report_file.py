#!/usr/bin/env python3
"""
Script that continually checks for the existence of the MCCS functional
test output file cucumber.json.

Script will timeout and waits between checks.
"""
import os.path
import time
import sys

TIME_TO_WAIT = 60
TIME_COUNTER = 0
FILE_PATH = "./testing/results/cucumber.json"

while not os.path.exists(FILE_PATH):
    time.sleep(1)
    TIME_COUNTER += 1
    if TIME_COUNTER == TIME_TO_WAIT:
        break

if TIME_COUNTER != TIME_TO_WAIT:
    if os.path.isfile(FILE_PATH):
        print(f"File appeared after {TIME_COUNTER} seconds")
        sys.exit(0)
    else:
        print(f"{FILE_PATH} isn't a file")
        sys.exit(1)
else:
    print(f"The file did not appear in {TIME_TO_WAIT} seconds")
    sys.exit(2)
