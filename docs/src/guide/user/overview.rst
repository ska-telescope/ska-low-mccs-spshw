========
Overview
========

Physically, the optical fibres from the station are routed to the RPF (remote processing facility) 
and CPF (central processing facility), where they are digitised and
the signal processing begins.

Visibility of the signal before this stage is provided by the Power and Signal Distribution System
(PaSD; see https://developer.skao.int/projects/ska-low-mccs-pasd/en/latest/user/index.html), which monitors
and controls power to the SKA-Low MCCS. Because multiple elements along the path — from the incoming sky
signal to the optical signal arriving at the RPF — require power, PaSD system can be a good indicator of the
health of the system.

Once the signal is digitised, the SPS software is responsible for processing the signals in accordance to 
configurations. Under normal operations this will be defined by the 
MCCS observation commands, ``Allocate`` and ``Configure`` (https://developer.skao.int/projects/ska-low-mccs/en/latest).

It is also important to flag up potential issues, we do this by exposing Health attributes, allowing us to drill
down to understand what element is at fault.

.. note::
   User guide content is still being written.
