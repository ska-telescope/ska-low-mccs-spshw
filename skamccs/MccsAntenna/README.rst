## LFAA Antenna Device Server

An implementation of the Antenna Device Server for the MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.

## Requirement

- PyTango >= 8.1.6
- devicetest (for using tests)
- sphinx (for building sphinx documentation)

## Installation

Run python setup.py install

If you want to build sphinx documentation,
run python setup.py build_sphinx

If you want to pass the tests, 
run python setup.py test

## Usage

Now you can start your device server in any
Terminal or console by calling it :

LfaaAntenna instance_name
