Subrack health
==============

Tango attributes and their configuration
-----------------------------------------

As with ``MccsTile`` (see :doc:`tile_health`), every monitoring point on
``MccsSubrack`` (temperatures, currents, voltages, PSU and fan status, and
so on) is exposed as a Tango attribute carrying a **quality factor**
(``tango.AttrQuality``). For numeric attributes, this quality factor is
computed by **Tango itself**, by comparing each new value against
``min_alarm``/``max_alarm``/``min_warning``/``max_warning`` thresholds held
as **configuration in the Tango database** - not by ``MccsSubrack`` code.
Where a value is currently unavailable (for example a PSU that has not
reported), ``MccsSubrack`` explicitly marks that attribute ``ATTR_INVALID``.

HealthRecorder
--------------

Like ``MccsTile``, ``MccsSubrack`` delegates ``healthState``/``healthReport``
derivation to
`HealthRecorder, documented here <https://developer.skao.int/projects/ska-low-mccs-common/en/latest/reference_material/health_recorder.html>`_,
which derives both purely from the worst Tango quality factor across a
configured set of the device's own attributes. Unlike ``MccsTile``,
``MccsSubrack`` uses the base ``HealthRecorder`` directly rather than a
subclass, since it has no per-group intermediate ``*Health`` attributes.

This only applies when the ``UseAttributesForHealth`` device property is
``True`` (the default, per ADR-115). When it is ``False``, ``MccsSubrack``
instead falls back to the legacy ``SubrackHealthModel``. As with ``MccsTile``,
``UseAttributesForHealth=False`` is **deprecated** and due to be removed
soon.

Monitored attributes and their subrack monitoring points
-----------------------------------------------------------

``MccsSubrack`` polls a nested ``health_status`` dictionary from the
subrack management board over its web interface (see
:doc:`subrack_driver`). Where an attribute's value lives at a nested path
in that dictionary, ``MccsSubrack`` records the path in
``_HEALTH_STATUS_MAP``, keyed the same way as ``MccsTile``'s
``attribute_monitoring_point_map``:

- the **key** is the Tango attribute name (for example
  ``psu1VoltageOut``);
- the **value** is the dictionary traversal path (a list of keys) used to
  look up that monitoring point in ``health_status`` (for example
  ``["psus", "voltage_out", "PSU1"]``).

.. csv-table:: Tango attribute to subrack monitoring point mapping
   :header: "Tango attribute", "health_status path"
   :widths: 30, 40

   "``internalVoltagesPOWERIN``", "``internal_voltages -> V_POWERIN``"
   "``internalVoltagesSOC``", "``internal_voltages -> V_SOC``"
   "``internalVoltagesARM``", "``internal_voltages -> V_ARM``"
   "``internalVoltagesDDR``", "``internal_voltages -> V_DDR``"
   "``internalVoltages2V5``", "``internal_voltages -> V_2V5``"
   "``internalVoltages1V1``", "``internal_voltages -> V_1V1``"
   "``internalVoltagesCORE``", "``internal_voltages -> V_CORE``"
   "``internalVoltages1V5``", "``internal_voltages -> V_1V5``"
   "``internalVoltages3V3``", "``internal_voltages -> V_3V3``"
   "``internalVoltages5V``", "``internal_voltages -> V_5V``"
   "``internalVoltages3V``", "``internal_voltages -> V_3V``"
   "``internalVoltages2V8``", "``internal_voltages -> V_2V8``"
   "``psu1Present``", "``psus -> present -> PSU1``"
   "``psu2Present``", "``psus -> present -> PSU2``"
   "``psu1PowerIn``", "``psus -> power_in -> PSU1``"
   "``psu2PowerIn``", "``psus -> power_in -> PSU2``"
   "``psu1PowerOut``", "``psus -> power_out -> PSU1``"
   "``psu2PowerOut``", "``psus -> power_out -> PSU2``"
   "``psu1VoltageIn``", "``psus -> voltage_in -> PSU1``"
   "``psu2VoltageIn``", "``psus -> voltage_in -> PSU2``"
   "``psu1VoltageOut``", "``psus -> voltage_out -> PSU1``"
   "``psu2VoltageOut``", "``psus -> voltage_out -> PSU2``"

The remaining healthful attributes (backplane/board temperatures, board
current, fan speeds, TPM currents/voltages/powers and so on) are not nested
and so need no traversal path - they are read directly off the
``health_status``/component-manager payload under their own name, via the
1:1 rename table ``_ATTRIBUTE_MAP``.

As with the map above, this only determines **which** raw monitoring point
feeds an attribute's value - Tango still determines that attribute's
quality factor automatically, from thresholds configured, 
exactly as described above. For how that quality feeds into
``healthState`` and ``healthReport``, see the generic algorithm described
under :doc:`tile_health`.
