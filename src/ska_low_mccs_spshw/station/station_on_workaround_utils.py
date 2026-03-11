#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This file contains temporary helper utilities for station on workaround."""
# Unfortunately incompatibility in dependencies means we can't import
# from aiv utils so we're making this code smell until the workaround is
# no longer needed.
# Functions in this file have been pulled from:
# https://gitlab.com/ska-telescope/ska-low/-/tree/main/src/aiv_utils
from __future__ import annotations

import logging
import queue
import re
import time
from collections import Counter, defaultdict
from functools import partial
from inspect import getfullargspec
from typing import Any, Callable, Union

import backoff
import numpy as np
import toolz
from ska_control_model import ResultCode
from tango import DevFailed, DeviceProxy, DevSource, DevState, EventType, Group
from tango.device_proxy import __update_enum_values

__all__ = [
    "ensure_tpms_on",
]

RESULTCODE_SUCCESS = frozenset([ResultCode.OK, ResultCode.STARTED, ResultCode.QUEUED])
LOG = logging.getLogger(__name__)


def _update_enum(dev: DeviceProxy, attr: str, value: Any) -> Any:
    """
    Cast attribute value to appropriate Enum type if applicable.

    :param dev: DeviceProxy instance.
    :param attr: Name of the attribute.
    :param value: Value to cast.
    :returns: The value cast to Enum type if applicable, otherwise unchanged.
    """
    # pylint: disable=protected-access
    attr_info = dev.__get_attr_cache().get(attr.lower())
    if not attr_info:
        # this populates DeviceProxy's internal caches - see DeviceProxy.__getattr__
        dev.__refresh_cmd_cache()
        dev.__refresh_attr_cache()
        attr_info = dev.__get_attr_cache()[attr.lower()]
    return __update_enum_values(attr_info, value)


def single_prop(dev: DeviceProxy, prop_name: str) -> str:
    """
    Return the first value of a device property.

    :param dev: DeviceProxy instance.
    :param prop_name: Name of the property.
    :returns: The first value of the property as a string.
    """
    return dev.get_property(prop_name)[prop_name][0]


def _yield_attr_values(devices: list[DeviceProxy], attr: str, timeout: float = None):
    """
    Subscribe to attribute on each device and yield (device, attribute value) tuples.

    :param devices: List of DeviceProxy instances.
    :param attr: Name of the attribute to subscribe to.
    :param timeout: Optional timeout in seconds.
    :yields: Tuple of (device, attribute value).
    """

    def _evt_val(evt):
        if evt.err:
            return None
        if evt.attr_value is None:
            return evt.device, None
        return evt.device, _update_enum(evt.device, attr, evt.attr_value.value)

    s_q = queue.SimpleQueue()
    subscriptions = [
        dev.subscribe_event(attr, EventType.CHANGE_EVENT, s_q.put, stateless=True)
        for dev in devices
    ]

    if timeout is not None:
        deadline = time.time() + timeout

        def get_fn():
            return s_q.get(timeout=max(0.0, deadline - time.time()))

    else:
        get_fn = s_q.get

    try:
        yield from filter(None, map(_evt_val, iter(get_fn, object())))
    finally:
        for dev, sub in zip(devices, subscriptions):
            dev.unsubscribe_event(sub)


# pylint: disable=too-many-branches,no-value-for-parameter,too-many-statements
def wait_for(  # noqa:C901
    devs: DeviceProxy | list[DeviceProxy],
    attr: str,
    desired_value,
    failed_value=None,
    timeout: float = 60.0,
    quiet: bool = False,
) -> None:
    """
    Wait until attribute of each device reaches a desired value or matches a predicate.

    :param devs: DeviceProxy or list of DeviceProxy instances.
    :param attr: Name of the attribute to wait for.
    :param desired_value: Value or predicate to wait for.
    :param failed_value: Value or predicate indicating failure.
    :param timeout: Maximum time to wait for each device.
    :param quiet: Suppress logging if True.
    :raises AssertionError: If device source is not DevSource.DEV.
    :raises Empty: If devices fail to reach desired value.
    :raises exc: If devices fail to reach desired value or reach fail value.
    """

    def default_predicate(expected, value, _):
        match expected, value:
            case list() | np.ndarray(), np.ndarray():
                return np.array_equal(value, expected)
            case set(), _:
                return value in expected
            case _:
                return value == expected

    # allow predicate to accept only value, or value and device
    desired_predicate_vararg: Union[Any, Callable[[Any], bool]] = (
        desired_value
        if callable(desired_value)
        else partial(default_predicate, desired_value)
    )
    failed_predicate_vararg: Union[Any, Callable[[Any], bool]] = (
        failed_value
        if callable(failed_value)
        else partial(default_predicate, failed_value)
    )
    if len(getfullargspec(desired_predicate_vararg).args) == 1:

        def desired_predicate(vararg, _):
            return desired_predicate_vararg(vararg)

    else:
        desired_predicate = desired_predicate_vararg

    if len(getfullargspec(failed_predicate_vararg).args) == 1:

        def failed_predicate(vararg, _):
            return failed_predicate_vararg(vararg)

    else:
        failed_predicate = failed_predicate_vararg

    if isinstance(devs, DeviceProxy):
        devs = [devs]

    if len(devs) == 0:
        return

    devsource_not_dev = [dev for dev in devs if dev.get_source() != DevSource.DEV]
    if devsource_not_dev:
        raise AssertionError(
            "Some devices not set to DevSource.DEV, which could lead to "
            f"inaccurate attribute reads: {format_trls(devsource_not_dev)}"
        )

    if not quiet:
        LOG.info(
            f"Waiting {timeout}s for attribute {attr} of {format_trls(devs)} "
            f"to reach {desired_value!r}"
        )

    devs_left = set(devs)
    devs_failed = set()
    devs_done = {}
    try:
        for dev, value in _yield_attr_values(devs, attr, timeout=timeout):
            if dev not in devs_left:
                continue
            if not quiet:
                LOG.debug(f"{dev.dev_name()}/{attr} = {value!r}")
            if failed_value is not None and failed_predicate(value, dev):
                devs_failed.add(dev)
                devs_left.remove(dev)
            if desired_predicate(value, dev):
                devs_left.remove(dev)
                devs_done[dev] = value
            if not devs_left:
                if devs_failed:
                    raise queue.Empty()
                break
    except queue.Empty:
        for dev in devs_left:
            try:
                value = _update_enum(dev, attr, dev[attr].value)
            except DevFailed as ex:
                LOG.warning(f"{dev} raised DevFailed reading attribute: {ex}")
            else:
                if desired_predicate(value, dev):
                    LOG.warning(
                        f"{dev} did not send an event, "
                        f"but attribute {attr} reached the desired value {value!r}"
                    )
                    devs_done[dev] = value
        devs_left -= devs_done.keys()
        if devs_left | devs_failed:
            errs = []
            if devs_left:
                errs.append(
                    f"didn't reach desired value {desired_value!r} "
                    f"for {format_trls(devs_left)}"
                )
            if devs_failed:
                errs.append(
                    f"reached fail value {failed_value!r} "
                    f"for {format_trls(devs_failed)}"
                )
            exc = ValueError(
                f"After {timeout}s, attribute {attr} " + ", and ".join(errs)
            )
            exc.failed_devices = devs_left.union(devs_failed)
            raise exc from None  # the queue.Empty is not useful information, drop it


def format_trls(devs):
    """
    Return a compact representation of device names by factoring out a common prefix.

    :param devs: List of device names or DeviceProxy instances.
    :returns: Condensed string representation of device names.
    """
    trls = sorted(dev if isinstance(dev, str) else dev.dev_name() for dev in devs)
    if len(trls) == 0:
        return ""
    if len(trls) == 1:
        return trls[0]

    # Split on regex word boundaries
    tokenised = [re.split(r"\b", trl) for trl in trls]

    # If all TRLs have the same number of tokens
    if len(set(len(tokens) for tokens in tokenised)) == 1:
        part_sets = [sorted(set(tokens)) for tokens in zip(*tokenised)]

        # If only one token differs between TRLs
        length_counts = Counter(len(part) for part in part_sets)
        if length_counts[1] == len(part_sets) - 1:
            # Construct and return the condensed format
            return "".join(
                part[0] if len(part) == 1 else f"({'|'.join(part)})"
                for part in part_sets
            )

    # Otherwise just join full TRLs with comma
    return ", ".join(trls)


def fq_dev_name(dev: DeviceProxy) -> str:
    """
    Return a fully-qualified device name for a DeviceProxy.

    :param dev: DeviceProxy instance.
    :returns: Fully-qualified device name as a string.
    """
    return f"{dev.get_db_host()}:{dev.get_db_port()}/{dev.dev_name()}"


def restart_devices(devs: list[DeviceProxy], force_restartserver: bool = False) -> None:
    """
    Restart devices without affecting other devices.

    :param devs: List of DeviceProxy instances to restart.
    :param force_restartserver: If True, force restart of device server.
    """
    dev_trl_map = {dev.dev_name(): dev for dev in devs}
    restart_trls = set(dev_trl_map)
    for dserver in [DeviceProxy(trl) for trl in {dev.adm_name() for dev in devs}]:
        ds_trls = {trl for cls, trl in [x.split("::") for x in dserver.QueryDevice()]}
        if ds_trls.issubset(restart_trls) or force_restartserver:
            LOG.warning(
                f"Restarting devices {ds_trls} by restarting {dserver.dev_name()}"
            )
            dserver.RestartServer()
        else:
            for trl in ds_trls & restart_trls:
                LOG.warning(f"Restarting device {trl} with Init()")
                dev_trl_map[trl].Init()


class group(Group):  # noqa: N801 pylint: disable=invalid-name
    """Like a tango.Group, but iterable, and sets source and timeout."""

    def get_device(self, name_or_index):
        proxy = super().get_device(name_or_index)
        proxy.set_timeout_millis(10000)
        proxy.set_source(DevSource.DEV)
        return proxy

    def __iter__(self):
        # pylint: disable=no-member
        return (self.get_device(trl) for trl in self.get_device_list())


@backoff.on_exception(backoff.expo, Exception, max_time=180.0)
def ensure_tpms_on(tpms: list[DeviceProxy]):
    """
    Brute force method to get TPMs ON reliably.

    :param tpms: list of TPM DeviceProxies
    """
    INIT_STATES = {"Initialised", "Synchronised"}  # noqa: N806
    ON_STATES = {DevState.ON, DevState.ALARM}  # noqa: N806

    def power_via_subrack(tpm: DeviceProxy, on: bool) -> None:
        subrack_trl = single_prop(tpm, "SubrackFQDN")
        subrack_bay = single_prop(tpm, "SubrackBay")
        subrack = DeviceProxy(subrack_trl)
        if on:
            subrack.PowerOnTpm(int(subrack_bay))
        else:
            subrack.PowerOffTpm(int(subrack_bay))

    tpms_grp = group("tpms")
    for tpm in tpms:
        tpms_grp.add(fq_dev_name(tpm))

    tpm_states = tpms_grp.read_attribute("tileProgrammingState")

    states = defaultdict(
        set,
        toolz.valmap(
            lambda replies: {tpms_grp.get_device(r.dev_name()) for r in replies},
            toolz.groupby(lambda v: v.get_data().value, tpm_states),
        ),
    )
    for state, state_tpms in states.items():
        print(f"{state}: {format_trls(state_tpms)}")

    to_powercycle = set()

    if states["NotProgrammed"]:
        print(f"Running Initialise for tpms {format_trls(states['NotProgrammed'])}")
    for tpm in states["NotProgrammed"]:
        if tpm.mcu_wd:
            print(f"TPM {tpm.dev_name()} has MCU_wd!")
            to_powercycle.add(tpm)
        else:
            tpm.Initialise()

    to_powercycle |= states["Off"] | states["Unconnected"]
    if to_powercycle:
        print(f"Powercycling tpms {format_trls(to_powercycle)}")
    for tpm in to_powercycle:
        power_via_subrack(tpm, on=False)
    try:
        wait_for(to_powercycle, "state", DevState.OFF, timeout=30)
    except ValueError as e:
        print(f"Some TPMs didn't turn off: {format_trls(e.failed_devices)}")
    for tpm in to_powercycle:
        power_via_subrack(tpm, on=True)
    try:
        wait_for(to_powercycle, "state", ON_STATES, timeout=30)
    except ValueError as e:
        print(f"Some TPMs didn't turn on: {format_trls(e.failed_devices)}")

    try:
        wait_for(tpms, "tileProgrammingState", INIT_STATES, timeout=45)
    except ValueError as e:
        print(f"Some TPMs are still not initialised: {format_trls(e.failed_devices)}")
        restart_devices(e.failed_devices, force_restartserver=True)
        wait_for(tpms, "tileProgrammingState", INIT_STATES, timeout=60)

        # </THORN-444 TPM Power Workaround Helpers>
        wait_for(tpms, "tileProgrammingState", INIT_STATES, timeout=60)

        # </THORN-444 TPM Power Workaround Helpers>
        wait_for(tpms, "tileProgrammingState", INIT_STATES, timeout=60)
