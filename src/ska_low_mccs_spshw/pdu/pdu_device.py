# -*- coding: utf-8 -*-
#
# This file is part of the SKA MCCS project
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE.txt for more info.
"""This module implements the PDU device."""

from __future__ import annotations  # allow forward references in type hints

import importlib.resources
import itertools
import os
import string
import sys
from pathlib import Path
from typing import Any, Generator, cast

import yaml
from pysnmp.smi.builder import MibBuilder
from pysnmp.smi.compiler import addMibCompiler
from ska_control_model import CommunicationStatus, HealthState, PowerState
from ska_snmp_device.snmp_component_manager import SNMPComponentManager
from ska_snmp_device.snmp_device import AttributePollingDevice
from ska_snmp_device.types import SNMPAttrInfo, attr_args_from_snmp_type
from ska_telmodel.data import TMData
from tango import AttrWriteType
from tango.server import device_property

from ska_low_mccs_spshw.pdu.pdu_health_model import PduHealthModel

__all__ = ["MccsPdu", "main"]


class MccsPdu(AttributePollingDevice):
    """An implementation of a PDU Tango device for MCCS."""

    DeviceDefinition = device_property(dtype=str, mandatory=True)
    Host = device_property(dtype=str, mandatory=True)
    Port = device_property(dtype=int, default_value=161)
    V2Community = device_property(dtype=str)
    V3UserName = device_property(dtype=str)
    V3AuthKey = device_property(dtype=str)
    V3PrivKey = device_property(dtype=str)
    MaxObjectsPerSNMPCmd = device_property(dtype=int, default_value=24)
    UpdateRate = device_property(dtype=float, default_value=3.0)

    # ---------------
    # Initialisation
    # ---------------
    def __init__(
        self: MccsPdu,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialise a new instance.

        :param args: positional arguments.
        :param kwargs: keyword arguments.
        """
        # This __init__ method is created for type-hinting purposes only.
        # Tango devices are not supposed to have __init__ methods,
        # And they have a strange __new__ method,
        # that calls __init__ when you least expect it.
        # So don't put anything executable in here
        # (other than the super() call).
        self._health_state: HealthState
        self._health_model: PduHealthModel
        self._dynamic_attrs: dict
        self._version_id = sys.modules["ska_low_mccs_spshw"].__version__

        super().__init__(*args, **kwargs)

    def init_device(self: MccsPdu) -> None:
        """Initialise the device."""
        try:
            super().init_device()

            device_name = f'{str(self.__class__).rsplit(".", maxsplit=1)[-1][0:-2]}'
            version = f"{device_name} Software Version: {self._version_id}"
            properties = f"Initialised {device_name} on: {self.Host}:{self.Port}"
            version_info = f"{self.__class__.__name__}, {self._build_state}"
            self.logger.info("\n%s\n%s\n%s", version_info, version, properties)

        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self.logger.error("Initialise failed: Incomplete server: %s", repr(ex))

    def delete_device(self: MccsPdu) -> None:
        """Delete the device."""
        try:
            self.logger.info("Deleting device")
            self.component_manager.stop_communicating()
        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self.logger.error("Failed to delete device %s", repr(ex))

    def _init_state_model(self: MccsPdu) -> None:
        """Initialise the state model."""
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN
        self._health_model = PduHealthModel(self._component_state_changed)
        self.set_change_event("healthState", True, False)
        self.set_archive_event("healthState", True, False)

    def load_device_definition(self: MccsPdu, filename: str) -> dict[str, Any]:
        """
        Return the parsed contents of the YAML file at filename.

        :param filename: configuration file from telmodel or yaml file to override

        :raises Exception: if not a valid ska_telmodel or file system configuration
        :return: the configuration dictionary
        """
        self.logger.info("loading device definition file %s", filename)
        tmdata = TMData()
        try:
            return tmdata[filename].get_dict()
        # pylint: disable=broad-exception-caught
        except Exception:
            self.logger.warning("%s is not an SKA_TelModel configuration", filename)
            try:
                path = Path(filename).resolve()
                self.logger.info("directory %s", os.getcwd())
                self.logger.info("loading yaml file %s", path)
                with open(path, encoding="utf-8") as def_file:
                    self.logger.info("loading yaml file %s", path)
                    return yaml.safe_load(def_file)
            except Exception as ex:
                self.logger.error("No configuration file %s to load", filename)
                raise ex

    def parse_device_definition(
        self: MccsPdu, definition: dict[str, Any]
    ) -> list[SNMPAttrInfo]:
        """
        Build attribute metadata from a deserialised device definition file.

        :param definition: device definition file

        :return: list of deserialised attribute metadata
        """
        # Keep this out of the loop so that we only create this thing once
        mib_builder = self._create_mib_builder()
        return [
            self._build_attr_info(mib_builder, attr_info)
            for attr_template in definition["attributes"]
            for attr_info in self._expand_attribute(attr_template)
        ]

    def _build_attr_info(
        self: MccsPdu, mib_builder: MibBuilder, attr: dict[str, Any]
    ) -> SNMPAttrInfo:
        """
        Build a SNMPAttrInfo describing the provided attribute.

        Using the relevant MIB files, we inspect the SNMP type and return
        useful metadata about the attribute in an SNMPAttrInfo, including
        suitable arguments to pass to tango.server.attribute().

        :param mib_builder: mib builder
        :param attr: attribute

        :return: SNMP attribute information
        """
        # Pop off the values we're going to use in this function. The rest will
        # be used as overrides to the generated tango.server.attribute() args.
        mib_name, symbol_name, *_ = oid = tuple(attr.pop("oid"))
        polling_period = attr.pop("polling_period", 0) / 1000

        # get metadata about the SNMP object definition in the MIB
        (mib_info,) = mib_builder.importSymbols(mib_name, symbol_name)

        # Build args to be passed to tango.server.attribute()
        attr_args = {
            "access": {
                "readonly": AttrWriteType.READ,
                "read-only": AttrWriteType.READ,
                "writeonly": AttrWriteType.WRITE,
                "write-only": AttrWriteType.WRITE,
                "readwrite": AttrWriteType.READ_WRITE,
                "read-write": AttrWriteType.READ_WRITE,
            }[mib_info.maxAccess],
            **attr_args_from_snmp_type(mib_info.syntax),
            **attr,  # allow user to override generated args
        }

        return SNMPAttrInfo(
            polling_period=polling_period,
            attr_args=attr_args,
            identity=oid,
        )

    def _create_mib_builder(self: MccsPdu) -> MibBuilder:
        """
        Initialise a MibBuilder that knows where to look for MIBs.

        :return: the mib builder
        """
        mib_builder: MibBuilder = MibBuilder()
        mib_builder.loadTexts = True

        # Adding a compiler allows the builder to fetch and compile novel MIBs.
        # mibs.pysnmp.com is built from https://github.com/lextudio/mibs.pysnmp.com
        # and contains thousands of standard MIBs and vendor MIBs for COTS hardware.
        # Extra MIBs can be dropped in ./mib_library, which will be searched first.
        miblib = str(
            importlib.resources.files("ska_low_mccs_spshw.pdu").joinpath("mib_library")
        )
        self.logger.info("adding mib_library %s", miblib)
        addMibCompiler(
            mib_builder,
            sources=[
                miblib,
                "https://mibs.pysnmp.com/asn1/@mib@",
            ],
        )
        return mib_builder

    def _expand_attribute(self: MccsPdu, attr: Any) -> Generator[Any, None, None]:
        """
        Yield templated copies of attr, based on the "indexes" key.

        "indexes" should be a list of N ranges [a, b], where a <= b. One
        attribute definition will be yielded for each element (i1, ..., iN)
        of the cartesian product of the provided ranges. The "name" field
        of each attribute will be formatted with name.format(i1, ..., iN).

        If "indexes" is not present, attr will be yielded unmodified. This
        function also performs some validation on the attribute definition.

        :param attr: the attribute

        :raises ValueError: formatting errors

        :yields: copies of the attribute
        """
        suffix = attr["oid"][2:]
        indexes = attr.pop("indexes", [])
        name = attr["name"]

        # Be kind, provide useful error messages
        replacements = [
            x for _, x, _, _ in string.Formatter().parse(name) if x is not None
        ]
        if indexes:
            if not replacements:
                raise ValueError(
                    f'Attribute name "{name}" contains no format specifiers, '
                    "but defines an index"
                )
        else:
            if replacements:
                raise ValueError(
                    f'Attribute name "{name}" contains format specifiers, '
                    "but no indexes were provided"
                )
            if not suffix:
                raise ValueError(
                    f'OID for attribute "{name}" must have a suffix - use'
                    " 0 for a scalar object"
                )

        index_ranges = (range(a, b + 1) for a, b in indexes)
        for element in itertools.product(*([i] for i in suffix), *index_ranges):
            index_vars = element[len(suffix) :]  # black wants this space T_T
            formatted_name = name.format(*index_vars)
            if not formatted_name.isidentifier():
                raise ValueError(
                    f'Attribute name "{formatted_name}" is not a valid '
                    "Python identifier"
                )
            # yield the tango attribute, the name modified by any index, if we are
            # dealing with tables and the associated full oid.
            # e.g  from the configuration file
            # name: spectrum_attr_{}
            # oid: [MY-MIB, tableObject]
            # indexes:
            # - [4, 6]
            # this would  yield
            # - name: spectrum_attr_4
            #   oid: [MY-MIB, tableObject, 4]
            # - name: spectrum_attr_5
            #   oid: [MY-MIB, tableObject, 5]
            # - name: spectrum_attr_6
            #   oid: [MY-MIB, tableObject, 6]
            yield {
                **attr,
                "name": formatted_name,
                "oid": [*attr["oid"], *index_vars],
            }

    def create_component_manager(self) -> SNMPComponentManager:
        """
        Create and return a component manager.

        :return: SNMPComponent manager
        """
        # This goes here because you don't have access to properties
        # until tango.server.BaseDevice.init_device() has been called
        dynamic_attrs = self.parse_device_definition(
            self.load_device_definition(self.DeviceDefinition)
        )
        self._dynamic_attrs = {attr.name: attr for attr in dynamic_attrs}

        assert (self.V2Community and not self.V3UserName) or (
            not self.V2Community and self.V3UserName
        ), "Can't be V2 & V3 simultaneously"

        if self.V2Community:
            authority = self.V2Community
        else:
            authority = {
                "auth": self.V3UserName,
                "authKey": self.V3AuthKey,
                "privKey": self.V3PrivKey,
            }

        return SNMPComponentManager(
            host=self.Host,
            port=self.Port,
            authority=authority,
            max_objects_per_pdu=self.MaxObjectsPerSNMPCmd,
            logger=self.logger,
            communication_state_callback=self._communication_state_changed,
            component_state_callback=self._component_state_changed,
            attributes=dynamic_attrs,
            poll_rate=self.UpdateRate,
        )

    def _communication_state_changed(
        self: MccsPdu,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_state: the status of communications between
            the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_disconnected",
            CommunicationStatus.ESTABLISHED: "component_on",
        }
        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        info_msg = f"Communication status is {communication_state}"
        self.logger.info(info_msg)
        self._health_model.update_state(communicating=True)

    def _component_state_changed(
        self: MccsPdu,
        fault: bool | None = None,
        power: PowerState | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param fault: whether the component has faulted or not
        :param power: unused in this implementation
        :param kwargs: state change parameters.
        """
        if "health" in kwargs:
            health = kwargs.pop("health")
            if self._health_state != health:
                self._health_state = cast(HealthState, health)
                self.push_change_event("healthState", health)
                self.push_archive_event("healthState", health)
        super()._component_state_changed(**kwargs)

        for attribute_name, value in kwargs.items():
            info_msg = f"Updating {attribute_name}, {value}"
            self.logger.info(info_msg)


# ----------
# Run server
# ----------


def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments
    :return: exit code
    """
    return cast(int, MccsPdu.run_server(args=args or None, **kwargs))


if __name__ == "__main__":
    main()
