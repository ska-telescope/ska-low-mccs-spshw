# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Utilities for checking calendar entries."""

import re
from datetime import datetime, timedelta
from typing import Any

import backoff
import recurring_ical_events
import requests
from icalendar import Calendar
from pytz import timezone

__all__ = ["CALENDAR_METADATA", "is_calendar_booked", "parse_duration"]

RESERVATION_CALENDAR_URL = (
    "https://confluence.skatelescope.org/rest/calendar-services/1.0"
    "/calendar/export/subcalendar/private/%s.ics"
)


CALENDAR_METADATA: dict[str, dict[str, Any]] = {
    "RAL": {
        "UID": "001afcabcce946c9ee9be34c1110951a7cd63006",
        "event_type_allowlist": [
            # Subrack 1
            "ed980302-93a7-487c-8a6b-d5989cf6877f",
            # Subrack 3
            "cdd6246b-1cd8-46d2-92b9-54ceec438235",
            # Subrack 4
            "0594d521-c84a-4f38-bdb6-d28c19fb7789",
            # Subrack 5
            "c2cc7177-90e8-4856-91a8-e508f977c559",
            # TPM 1.2
            "07cb51cf-605d-473a-8650-0e7f4fe90828",
        ],
    },
}
UNITS = {
    "s": timedelta(seconds=1),
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
}


@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
    max_tries=5,
)
def request_calendar(calendar_ics_url: str) -> requests.Response:
    """
    Request a calendar from the given URL and return the requests response.

    :param calendar_ics_url: URL of the calendar to request.
    :return: requests response.
    """
    response = requests.get(calendar_ics_url, timeout=30)
    response.raise_for_status()  # raise for 4xx/5xx errors
    return response


def is_calendar_booked(  # pylint: disable=too-many-locals
    calendar_uid: str,
    event_type_allowlist: list[str],
    expected_runtime: timedelta,
    required_event_name: str | None = None,
    author: str = "",
) -> bool | list[Any]:
    """
    Return if calendar is booked within input time range.

    :param calendar_uid: UID of Confluence calendar to check.
    :param event_type_allowlist: List of event type IDs to ignore
        when checking for clashes.
    :param expected_runtime: How far in the future to check for clashes.
    :param required_event_name: if supplied, the search window
        must be fully covered by an event of this name.
    :param author: the email address of who triggered the job

    :return: is calendar is booked.
    """
    # Get the start and end time of calendar range to check
    search_start = datetime.now(tz=timezone("Europe/London")).replace(microsecond=0)
    search_end = search_start + expected_runtime

    # Download the calendar ics file
    calendar_ics_url = RESERVATION_CALENDAR_URL % calendar_uid
    print(f"Getting ICS file from: {calendar_ics_url}")
    response = request_calendar(calendar_ics_url=calendar_ics_url)
    calendar = Calendar.from_ical(response.text)

    # Loop over all calendar events and return the ones that can not be ignored
    ignore_all = "*" in event_type_allowlist
    events = recurring_ical_events.of(calendar).between(search_start, search_end)

    print(f"Events between {search_start} and {search_end}:")

    clashing_events = []
    required_event_present = not required_event_name
    for event in events:
        start = event["DTSTART"].dt
        end = event["DTEND"].dt
        end_time = end.time() if hasattr(end, "time") else end

        # Confluence handles summary strangely. SUMMARY sometimes
        # contains both the title and the DESCRIPTION; the title alone
        # isn't available anywhere
        summary = event["SUMMARY"].removesuffix(": " + event["DESCRIPTION"])
        if summary == required_event_name and start < search_start <= search_end < end:
            required_event_present = True

        event_type_id = event["CUSTOM-EVENTTYPE-ID"]
        ignored = ignore_all or event_type_id in event_type_allowlist

        organiser = event["ORGANIZER"]

        mail_addr = organiser.split(":")[1]

        diff_author = False
        if mail_addr not in author:
            diff_author = True
            print(
                "Timeslot not booked by the person who triggered this job, "
                f"booking: {mail_addr}, job triggerer: {author}"
            )

        if "PIPELINE_TEST" in event["DESCRIPTION"]:
            ignored = True
            print("PIPELINE_TEST keyword found in desc, continuing")

        if not ignored and diff_author:
            clashing_events.append(event)

        print(f"{' ' if ignored else 'X'} {start} until {end_time} {summary}")

    if clashing_events:
        print(f"{len(clashing_events)} clashing event(s) in allotted time")
    else:
        print("No clashing events in timeslot")

    if not required_event_present:
        print(
            f'Required event "{required_event_name}" is not present '
            "or does not cover allotted time"
        )
    elif required_event_name:
        print(
            f'Required event "{required_event_name}" is present '
            "and covers the allotted time"
        )

    return clashing_events or not required_event_present


def parse_duration(duration_str: str) -> timedelta:
    r"""
    Parse duration string matching '\d+[smh]' into timedelta.

    :param duration_str: a duration in the format '\d+[smh]' where
        's' means seconds, 'm' means minutes, and 'h' means hours.
    :return: a timedelta representing the duration
    :raises ValueError: when no match found.
    """
    unit_strs = "".join(UNITS)
    pattern = re.compile(rf"(\d+)([{unit_strs}])")
    if pattern.fullmatch(duration_str) is None:
        raise ValueError("No match found")
    __match = pattern.fullmatch(duration_str)
    assert __match is not None
    number_str, unit = __match.groups()
    return UNITS[unit] * int(number_str)
