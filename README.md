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

To collect one data point from a board. For this example the ID is 13 and the serial port is at `/dev/ttyUSB0`.

```console
uw-pyrometer measure --device_id 13 /dev/ttyUSB0
```

To collect the average of 5 samples, taken every 200 ms

```console
uw-pyrometer measure -d 13 --average 5 --interval 0.2 /dev/ttyUSB0
```

A continuous display is also possible

```console
uw-pyrometer measure -d 13 -n 0 /dev/ttyUSB0
```

For more information, run

```console
uw-pyrometer measure --help
```

This example sets the feedback potentiometer. Be mindful that these
values only remain until powering the board off. The first value (20) is for the
thermopile. The second (15) is for the thermistor.

```console
uw-pyrometer gain -d 13 /dev/ttyUSB0 20 15
```

### Troubleshooting

On some platforms, you may need to replace the `uw-pyrometer` command with `python -m uw-pyrometer`.

Be sure the `python` path matches the package installation environment.

## License

`uw-pyrometer` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
