# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This file contains a script for checking if the calendar is booked."""


import argparse
import sys

from utils import CALENDAR_METADATA, is_calendar_booked, parse_duration


def main() -> None:
    """Entry main function."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--calendar",
        type=str,
        choices=["RAL"],
        default="RAL",
        help="Calendar to check (only RAL supported)",
    )
    parser.add_argument(
        "--expected-runtime",
        type=parse_duration,
        default="30m",
        help="How far in the future to check for clashing events.",
    )
    parser.add_argument(
        "--required-event-name",
        type=str,
        help="Notebooks will only run if a calendar event of this name "
        "covers the time window implied by --expected-runtime.",
    )
    args = parser.parse_args()

    calendar_meta = CALENDAR_METADATA[args.calendar]

    if is_calendar_booked(
        calendar_meta["UID"],
        calendar_meta["event_type_allowlist"],
        args.expected_runtime,
        required_event_name=args.required_event_name,
    ):
        # this lets us differentiate from unexpected errors, in pipelines etc
        sys.exit(10)


if __name__ == "__main__":
    main()
