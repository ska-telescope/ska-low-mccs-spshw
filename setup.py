#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import setuptools

# pylint: disable=invalid-name
setup_dir = os.path.dirname(os.path.abspath(__file__))
release_module = {}
release_filename = os.path.join(setup_dir, 'skamccs', 'release.py')
# pylint: disable=exec-used
exec(open(release_filename).read(), release_module)

setuptools.setup(
    name=release_module["name"],
    description=release_module["description"],
    version=release_module["version"],
    author=release_module["author"],
    author_email=release_module["author_email"],
    license=release_module["license"],
    packages=setuptools.find_packages(),
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
    setup_requires=[
        'pytest-runner',
        'sphinx',
        'sphinx_rtd_theme'
    ],
    install_requires=[
        # should be pulled in by lmcbaseclasses but isn't
        "pytango >= 9.3.1",
        "lmcbaseclasses >= 0.5.0"
        # pulled in by lmcbaseclasses
        # "ska_logging >= 0.2.1",
    ],
    tests_require=[
        'pytest',
        'pytest-cov',
        'pytest-json-report',
        'pycodestyle',
        'pytest-pylint',
        'pytest-json-report',
        'coverage',
        'pytest-xdist',
        'pylint2junit',
        'mock'
    ],
    keywords="lmc mccs tango ska",
    zip_safe=False)
