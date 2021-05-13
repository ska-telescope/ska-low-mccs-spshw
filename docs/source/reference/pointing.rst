################################
 MCCS Prototype Pointing Control
################################

*******
Purpose
*******

MCCS must act on received pointing commands to steer each station to the
required sky coordinates. Since SKA-Low is an aperture array telescope
pointing is achieved by setting appropriate delays on the signals received
from each receptor such that signals from the required direction add coherently.

The required calculation involves a projection from the pointing direction
onto the receptor positions. This is readily achieved with `numpy`.

The code used has been demonstrated to work with AAVS. Here we start adapting
it to MCCS and provide a CLI for evaluation purposes. Delays (and delay rates,
produced for progressive delay adjustment to track a source across the sky)
are saved a file, for subsequent checks.

As a guide to the required resources we also time the calculation. This is
done both with a direct call to the calculation function and also assigning
it as a worker for one or more multiprocessing processes, to see if this
achieves in a speed-up.

****
Code
****

The code in point_station.py is taken from AAVS.
Minimal adapatations have been made.

***
CLI
***

The main addition is a CLI made with Fire.

The commands are as follows:

* `statpos lat lon height`
  * Set the station reference position
  * `lat` and `lon` use decimal degrees
  * `height` is the ellipsoidal height, not orthometric

* `displacements file`
  * Read the element displacements from `file` - AAVS format
  
* `azel az el`
  * Point the station to an azimuth and elevation
  * `az` and `el` are read by astropy and may be of the form `180.0d 45.0d`
  
* `radec ra, dec`
  * Point the station to right ascension and declination and track
  * `ra` and `dec` are read by astropy and may be of the form `180.0d 45.0d` or `12.0h 45.d`

* `sun`
  * Point the station towards the Sun and track

* `startat when scale`
  * Set the starting time for tracking (`radec` or `sun`)
  * e.g. `startat '2021-05-09T23:00:00' utc`
  
* `sequence count interval`
  * Generate a sequence of tracked pointings.
  * `count` is the number of pointings and `interval` the time step in seconds
  
* `single`
  * Generate a single pointing
  
* `msequence count interval nproc`
  * This is a multiprocessing version of `sequence`.
  * `count` is the number of pointings and `interval` the time step in seconds
  * Additionally `nproc` is the number of processes to fork.
  
* `write filename`
  * Write the generated pointing frame(s) to a file as csv.
  * No more commands are read.
  
* `done`
  * No more commands are read.
  * Not needed if you finished with `write`.

Here is an example command:

`python3 src/ska_low_mccs/point_station.py statpos -26.8247 116.7644 346.36 displacements testing/data/AAVS2_loc_italia_190429.txt sun startat '2021-05-09T23:00:00' utc msequence 720 10 4 write testing/results/sun_10s2.txt`

* The station position is set to the nominal array centre.
* Displacements are read from the included AAVS file.
* Pointing is towards the Sun.
* A start time of 2021-05-09 23:00:00 UTC is set (join the time to the date with the `T` character).
* Multiprocessing with 4 processes is used to generate 720 pointing frames in 10-second intervals.
* The results are written to a file (ensure that the directory exists).
