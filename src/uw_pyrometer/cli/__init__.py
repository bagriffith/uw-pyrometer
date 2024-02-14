import time
import logging
import click

from uw_pyrometer import pyrometer
from uw_pyrometer.__about__ import __version__

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=False)
@click.version_option(version=__version__, prog_name="uw_pyrometer")
def uw_pyrometer():
    pass


@uw_pyrometer.command()
@click.argument('serial_path', type=str)
@click.option('--device_id', '-d', default=0, type=click.IntRange(0, 255))
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--broadcast', '-b', default=False, is_flag=True)
@click.option('--interval', '-i', default=1.0, type=click.FloatRange(min_open=0),
              help='Polling interval in seconds.')
@click.option('--samples', '-n', default=None, type=click.IntRange(min=0),
              help='Number of samples to collect. 0 runs indefinitely. If not'
              'provided, sample the number of points to average.')
@click.option('--average', '-a', default=1, type=click.IntRange(min=1),
              help='Set number of points to average over.')
@click.option('--show_prelim', default=False, is_flag=True,
              help='Show values before average samples are collected.')
@click.option('--no_clear', default=False, is_flag=True,
              help='Leave old samples instead of clearing console.')
def measure(serial_path, device_id, verbose, broadcast, interval, samples, average, show_prelim, no_clear):
    if verbose:
        pyrometer.logger.setLevel('DEBUG')
        pyrometer.logger.addHandler(logging.StreamHandler())
        logger.setLevel('DEBUG')
        logger.addHandler(logging.StreamHandler())


    if samples is None:
        samples = average

    if (average > samples) and (samples > 0):
        logger.warning('%s samples not enough for %s point averaging', samples, average)

    device = pyrometer.PyrometerSerial(device_id, serial_path)
    samples_taken = 0
    samples_history = {'Reference': [], 'Thermistor': [], 'Thermopile': []}
    while (samples_taken < samples) or (samples == 0):
        if samples_taken > 0:
            time.sleep(interval)
        try:
            ref, tr, tp = device.get_measurement(broadcast=broadcast)
        except TimeoutError:
            click.echo('Read timed out.')
            continue

        samples_history['Reference'].append(ref)
        samples_history['Thermistor'].append(tr)
        samples_history['Thermopile'].append(tp)
        samples_history.update({key: value[-average:]
                                for key, value in samples_history.items()})
        logger.debug(samples_history)
        samples_taken += 1

        if (samples_taken >= average) or show_prelim:
            separator = '*:' if samples_taken < average else ':'

            if average != (1 if show_prelim else samples) and not verbose:
                # If more than one value is displayed
                if no_clear:
                    click.echo()
                else:
                    click.clear()

            for key, value in samples_history.items():
                voltage = device.adc_to_voltage(sum(value)/len(value))
                click.echo(f'{key+separator:<13}{voltage:1.2f} V')


@uw_pyrometer.command()
@click.argument('serial_path', type=str)
@click.argument('thermopile', type=click.IntRange(0, 255))
@click.argument('thermistor', type=click.IntRange(0, 255))
@click.option('--device_id', '-d', default=0, type=click.IntRange(0, 255))
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--broadcast', '-b', default=False, is_flag=True)
def gain(serial_path, thermopile, thermistor, device_id, verbose, broadcast):
    if verbose:
        pyrometer.logger.setLevel('DEBUG')
        pyrometer.logger.addHandler(logging.StreamHandler())
        logger.setLevel('DEBUG')
        logger.addHandler(logging.StreamHandler())

    device = pyrometer.PyrometerSerial(device_id, serial_path)
    device.set_gains(thermopile, thermistor, broadcast)
