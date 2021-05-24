======================================================
TPM Driver module (ska_low_mccs.tile.tpm_driver)
======================================================
The driver interfaces with a HwTile object, directly derived from the aavs-system
pyaavs package, which in turn uses the pyfabil package for interfacing with the 
board and the individual firmware modules. 

The structure of the software is based on the pyaavs.board.TPM object. This object
loads an application specific plugin (tpm_test_firmware, in the 
ska_low_mccs.tile.plugin package) which in turn loads from pyaavs the 
required plugins for the tile firmware. The HwTile object instantiates
the TPM object, and direct the requests to the appropriate plugins. 
The HwTile is actually implemented as a factory, which loads the correct 
Tile device for the board version (1.2 or 1.6) 

.. toctree::
   :maxdepth: 2

.. automodule:: ska_low_mccs.tile.tpm_driver
   :members:
