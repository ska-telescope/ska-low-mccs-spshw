======================================
MccsTile ConfigureTestGenerator schema
======================================

Schema for MccsTile's ConfigureTestGenerator command

**********
Properties
**********

* **set_time** (string): Time to start the generator, in UTC ISO format.

* **tone_frequency** (number): Tone 1 frequency in Hz of DDC 0.

* **tone_amplitude** (number): Tone 1 peak amplitude, normalized to 31.875 ADC units, resolution 0.125 ADU.

* **tone_2_frequency** (number): Tone 2 frequency in Hz of DDC 1.

* **tone_2_amplitude** (number): Tone 2 peak amplitude, normalized to 31.875 ADC units, resolution 0.125 ADU.

* **noise_amplitude** (number): Amplitude of pseudorandom noise normalized to 26.03 ADC units, resolution 0.102 ADU.

* **pulse_frequency** (integer): Code for pulse frequency. Range 0 to 7: 16,12,8,6,4,3,2 times frame frequency. Minimum: 0. Maximum: 7.

* **pulse_amplitude** (number): pulse peak amplitude, normalized to 127.5 ADC units, resolution 0.5 ADU.

* **delays** (array): delays to apply to the ADC streams. Positive values add to the delay. Length must be equal to 32.

  * **Items** (number)

* **adc_channels** (array): ADC channels.

  * **Items** (integer)

