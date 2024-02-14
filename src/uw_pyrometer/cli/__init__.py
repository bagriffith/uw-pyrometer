import time
import logging
import click

from uw_pyrometer import pyrometer
from uw_pyrometer.__about__ import __version__

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
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
@click.option('--show_prelim', '-s', default=False, is_flag=True,
              help='Show values before average samples are collected.')
def measure(serial_path, device_id, verbose, broadcast, interval, samples, average, show_prelim):
    if verbose:
        pyrometer.logger.setLevel('DEBUG')
        pyrometer.logger.addHandler(logging.StreamHandler())
    
    if samples is None:
        samples = average

    if (average < samples) and (samples > 0):
        logger.warning('%s samples not enough for %s point averaging', samples, average)

    device = pyrometer.PyrometerSerial(device_id, serial_path)
    samples_taken = 0
    samples_history = {'Reference': [], 'Thermistor': [], 'Thermopile': []}
    while (samples_taken < samples) or (samples == 0):
        if samples_taken > 0:
            time.sleep(interval)
            if (samples_taken >= average) or show_prelim:
                click.echo()
        try:
            ref, tr, tp = device.get_measurement(broadcast=broadcast)
            samples_history['Reference'].append(ref)
            samples_history['Thermistor'].append(tr)
            samples_history['Thermopile'].append(tp)
            samples_taken += 1

            for key in samples_history:
                samples_history[key] = samples_history[key][-average:]
                separator = '*:' if samples_taken < average else ':'
                if (samples_taken >= average) or show_prelim:
                    value = device.adc_to_voltage(sum(samples_history[key])/len(samples_history[key]))
                    click.echo(f'{key+separator:<14}{value:1.3f}')
        except TimeoutError:
            click.echo('Read timed out.')

uw_pyrometer.add_command(measure)
