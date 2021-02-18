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
release_filename = os.path.join(setup_dir, "src", "ska", "low", "mccs", "release.py")
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
    packages=setuptools.find_namespace_packages(where="src"),
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
            "MccsAntenna=ska.low.mccs.antenna.antenna_device:main",
            "MccsAPIU=ska.low.mccs.apiu.apiu_device:main",
            "MccsController=ska.low.mccs.controller.controller_device:main",
            "MccsSubarray=ska.low.mccs.subarray:main",
            "MccsSubarrayBeam=ska.low.mccs.subarray_beam:main",
            "MccsSubrack=ska.low.mccs.subrack.subrack_device:main",
            "MccsStation=ska.low.mccs.station:main",
            "MccsStationBeam=ska.low.mccs.station_beam:main",
            "MccsTile=ska.low.mccs.tile.tile_device:main",
            "MccsTelState=ska.low.mccs.tel_state:main",
            "mccs-controller=ska.low.mccs.controller.controller_cli:main",
            "mccs-tile=ska.low.mccs.tile.tile_cli:main",
        ]
    },
    install_requires=[
        "lmcbaseclasses >= 0.6.4",
        "pytango >= 9.3.3",
        "jsonschema >= 3.2.0",
        "fire",
    ],
    zip_safe=False,
)
