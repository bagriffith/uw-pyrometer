import time
import logging
import click

from uw_pyrometer import pyrometer
from uw_pyrometer.__about__ import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="uw_pyrometer")
def uw_pyrometer():
    pass


@uw_pyrometer.command()
@click.argument('serial_path', type=str)
@click.option('--device_id', '-d', default=0, type=click.IntRange(0, 255))
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--broadcast', '-b', default=False, is_flag=True)
def measure(serial_path, device_id, verbose, broadcast):
    if verbose:
        pyrometer.logger.setLevel('DEBUG')
        pyrometer.logger.addHandler(logging.StreamHandler())

    device = pyrometer.PyrometerSerial(device_id, serial_path)
    while click:
        try:
            ref, tr, tp = device.get_measurement(convert=True, broadcast=broadcast)
            click.echo(f'Reference:   {ref:1.3f}')
            click.echo(f'Thermistor:  {tr:1.3f}')
            click.echo(f'Thermopile:  {tp:1.3f}')
            click.echo()
        except TimeoutError:
            click.echo('Read timed out.')
        time.sleep(1.)


uw_pyrometer.add_command(measure)
