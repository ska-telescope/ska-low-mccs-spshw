#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standard setup.py script.
"""
import os
import setuptools

# pylint: disable=invalid-name
setup_dir = os.path.dirname(os.path.abspath(__file__))
release_module = {}
release_filename = os.path.join(setup_dir, "src", "ska_low_mccs", "release.py")
# pylint: disable=exec-used
exec(open(release_filename).read(), release_module)

setuptools.setup(
    name=release_module["name"],
    description=release_module["description"],
    version=release_module["version"],
    author=release_module["author"],
    author_email=release_module["author_email"],
    license=release_module["license"],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    package_data={"": ["schemas/*.json"]},
    url=release_module["url"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Astronomy",
    ],
    platforms=["OS Independent"],
    keywords="lmc mccs tango ska",
    entry_points={
        "console_scripts": [
            "MccsAntenna=ska_low_mccs.antenna.antenna_device:main",
            "MccsAPIU=ska_low_mccs.apiu.apiu_device:main",
            "MccsController=ska_low_mccs.controller.controller_device:main",
            "MccsSubarray=ska_low_mccs.subarray:main",
            "MccsSubarrayBeam=ska_low_mccs.subarray_beam:main",
            "MccsSubrack=ska_low_mccs.subrack.subrack_device:main",
            "MccsStation=ska_low_mccs.station:main",
            "MccsStationBeam=ska_low_mccs.station_beam:main",
            "MccsTile=ska_low_mccs.tile.tile_device:main",
            "MccsTelState=ska_low_mccs.tel_state:main",
            "mccs-controller=ska_low_mccs.controller.controller_cli:main",
            "mccs-tile=ska_low_mccs.tile.tile_cli:main",
        ]
    },
    install_requires=[
        "ska-tango-base >= 0.9.1",
        "pytango >= 9.3.3",
        "jsonschema >= 3.2.0",
        "fire",
        "requests",
    ],
    zip_safe=False,
)
