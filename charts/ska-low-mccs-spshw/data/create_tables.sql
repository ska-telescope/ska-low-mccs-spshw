-- Script to create necessary table(s) for calibration database
CREATE TABLE tab_mccs_calib
(id serial NOT NULL PRIMARY KEY,
creation_time timestamp NOT NULL,
outside_temperature real NOT NULL,
frequency_channel smallint NOT NULL,
calibration real[] NOT NULL
);
