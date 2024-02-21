# uw_pyrometer

**Table of Contents**

- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Installation

```console
pip install uw-pyrometer 
```

## Examples

Collect one data point from a board. For this example the ID is 13 and the
serial port is at `/dev/ttyUSB0` and yaml calibration file is at
`calibration_path.yaml`. The feedback potentiometers are set to bytes 20 for
the thermopile and 15 for the thermistor. These can be adjusted to keep the
values in the ADC range.

```console
uw-pyrometer measure-physical --device_id 13 -c calibration_path.yaml -g 20 15 /dev/ttyUSB0
```

To average 5 samples, taken every 200 ms

```console
uw-pyrometer measure-physical -d 13 --average 5 --interval 0.2 /dev/ttyUSB0
```

For more information, run

```console
uw-pyrometer measure-physical --help
```

There are also the command `uw-pyrometer measure-adc` which can measure ADC
voltage without conversion. The `uw-pyrometer gain` can set the gain values
without taking a measurement.

### Troubleshooting

On some platforms, you may need to replace the `uw-pyrometer` command
with `python -m uw-pyrometer`.

Be sure the `python` path matches the package installation environment.

## License

`uw-pyrometer` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
