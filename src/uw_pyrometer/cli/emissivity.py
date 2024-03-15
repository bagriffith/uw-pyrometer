import logging
import click
#import matplotlib
#matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from uw_pyrometer import emissivity, pyrometer, omega_controller, cli
from uw_pyrometer.__about__ import __version__

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=False)
@click.version_option(version=__version__, prog_name="emissivity-routine")
def emissivity_routine():
    pass

@emissivity_routine.command()
@click.argument('data_path', type=click.Path(exists=False))
@click.option('--output', '-o', default=None, type=click.Path(exists=False),
              help='Output figure path.')
def plot(data_path, output):
    with open(data_path, encoding='utf8') as f:
        header = f.readline().strip().split(',')
        data = {k: [] for k in header}
        for row in f.readlines():
            for k, v in zip(header, row.strip().split(',')):
                data[k].append(float(v))

    plt.style.use(emissivity.PLOT_STYLE)
    vis = emissivity.EmissivityVis()
    t_lim = (min(data['block_temp'])-10, max(data['block_temp'])+10)
    vis.set_txlim(*t_lim)
    e, bg = emissivity.analyze_emissivity(data, vis)
    # vis.ax.set_ylim([1e6*bg+e*x for x in vis.ax.get_xlim()])
    print('Emissivity:', f'{e:.3f}')
    print('Background:', f'{1e6*bg:.1f} uW')

    if output is None:
        plt.figure().canvas.manager.canvas.figure = vis
        plt.show(block=True)
    else:
        vis.savefig(output)


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
@click.option('--output', '-o', default=None, type=click.Path(exists=False),
              help='Output csv path.')
@click.option('--verbose', '-v', default=False, is_flag=True)
@click.option('--log', '-l', default=False, is_flag=True)
def read(tp_serial, temp_serial, temps, device_id,
         calibration, samples, interval, plot, output, verbose, log):
    # Setup log
    debug = verbose or log
    pyrometer.logger.setLevel('DEBUG' if debug else 'WARNING')
    emissivity.logger.setLevel('DEBUG' if debug else 'WARNING')
    logger.setLevel('DEBUG' if debug else 'WARNING')
    logger.handlers.clear()
    emissivity.logger.handlers.clear()
    pyrometer.logger.handlers.clear()
    handler = logging.FileHandler('emissivity.log') if log else logging.StreamHandler()
    logger.addHandler(handler)
    pyrometer.logger.addHandler(handler)
    emissivity.logger.addHandler(handler)
    logger.info('Starting for temps: %s', temps)

    tp_dev = pyrometer.PyrometerSerial(device_id, tp_serial, calibration)
    temp_dev = omega_controller.omega_pid(port=temp_serial)
    emissivity.run(tp_dev, temp_dev, temps, samples, interval, plot, output)


@emissivity_routine.command()
@click.argument('serial_path', type=str)
def test(serial_path):
    temp_dev = omega_controller.omega_pid(port=serial_path)
    emissivity.test(temp_dev)
