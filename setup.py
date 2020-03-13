#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import setuptools

setup_dir = os.path.dirname(os.path.abspath(__file__))
RELEASE = {}
release_filename = os.path.join(setup_dir, 'skamccs', 'release.py')
exec(open(release_filename).read(), RELEASE)


setuptools.setup(
    name=RELEASE["name"],
    description=RELEASE["description"],
    version=RELEASE["version"],
    author=RELEASE["author"],
    author_email=RELEASE["author_email"],
    license=RELEASE["license"],
    packages=setuptools.find_packages(),
    include_package_data=True,
    scripts=[],
    url=RELEASE["url"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Astronomy"],
    platforms=["OS Independent"],
    setup_requires=[
        'pytest-runner',
        'sphinx',
    ],
    install_requires=[
        # should be pulled in by lmcbaseclasses but isn't
        "pytango >= 9.3.1",
        # pulled in by lmcbaseclasses
        # "ska_logging >= 0.2.1",
        "lmcbaseclasses"
    ],
    tests_require=[
        'pytest',
        'pytest-cov',
        'pytest-json-report',
        'pycodestyle',
    ],
    keywords="lmc mccs tango ska",
    zip_safe=False)
