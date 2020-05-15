#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Standard setup.py script """
import os
import setuptools

# pylint: disable=invalid-name
setup_dir = os.path.dirname(os.path.abspath(__file__))
release_module = {}
release_filename = os.path.join(setup_dir, 'src', 'ska', 'mccs', 'release.py')
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
    include_package_data=True,
    scripts=[],
    url=release_module["url"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Astronomy"],
    platforms=["OS Independent"],
    keywords="lmc mccs tango ska",
    entry_points={
        "console_scripts": [
            "MccsMaster=ska.mccs.master:main",
            "MccsSubarray=ska.mccs.subarray:main",
            "MccsStation=ska.mccs.station:main",
            "MccsStationBeam=ska.mccs.station_beam:main",
            "MccsTile=ska.mccs.tile:main",
        ]
    },
    install_requires=["lmcbaseclasses >= 0.5.1",
                      "pytango >= 9.3.1"],
    zip_safe=False)
