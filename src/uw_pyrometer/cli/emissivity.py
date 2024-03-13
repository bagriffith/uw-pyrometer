import logging
import click

from uw_pyrometer import emissivity, pyrometer, omega_controller, cli
from uw_pyrometer.__about__ import __version__

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=False)
@click.version_option(version=__version__, prog_name="emissivity-routine")
def emissivity_routine():
    pass


@emissivity_routine.command()
@click.argument('tp_serial', type=str)
@click.argument('temp_serial', type=str)
@click.argument('temps', type=float, nargs=-1)
@click.option('--device_id', '-d', default=0, type=click.IntRange(0, 254))
@click.option('--calibration', '-c', default=None, type=cli.Calibration(),
              help='Path to a yaml calibration file.')
@click.option('--samples', '-n', default=None, type=click.IntRange(min=0),
              help='Number of samples to collect. 0 runs indefinitely. If not'
              'provided, sample the number of points to average.')
@click.option('--interval', '-i', default=1.0, type=click.FloatRange(min_open=0),
              help='Polling interval in seconds.')
@click.option('--plot', '-p', default=False, is_flag=True)
@click.option('--output', '-0', default=None, type=click.Path(exists=True),
              help='Output csv path.')
def read(tp_serial, temp_serial, temps, device_id,
         calibration, samples, interval, plot):
    tp_dev = pyrometer.PyrometerSerial(device_id, tp_serial, calibration)
    temp_dev = omega_controller.omega_pid(port=temp_serial)
    emissivity.run(tp_dev, temp_dev, temps, samples, interval, plot)


@emissivity_routine.command()
@click.argument('serial_path', type=str)
def test(serial_path):
    temp_dev = omega_controller.omega_pid(port=serial_path)
    emissivity.test(temp_dev)
