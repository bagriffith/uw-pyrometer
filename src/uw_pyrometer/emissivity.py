import time
import asyncio
import logging
from importlib.resources import files as imp_files
import numpy as np
import matplotlib.pyplot as plt
import uw_pyrometer

T_DEADBAND = 0.2
TEST_TIMEOUT = 600  # Seconds
data = np.loadtxt(imp_files(uw_pyrometer)/'data/bandpass.csv', delimiter=',')
BP_TEMP = data[:, 0]
BP_VAL = data[:, 1]

PLOT_STYLE = imp_files(uw_pyrometer) / 'plot_style.mplstyle'

logger = logging.getLogger(__name__)

class EmissivityVis(plt.Figure):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.make_emissivity_ax()

    def set_txlim(self, l_lim, r_lim):
        k = uw_pyrometer.pyrometer.RESPONSIVITY * bandpass(22.0)
        x_lim = [1e6*k*to_k(x)**4 for x in (l_lim, r_lim)]
        self.ax.set_xlim(*x_lim)

    def make_emissivity_ax(self):
        self.ax = self.add_subplot(111)
        self.ax.set_xlabel(r'Blackbody Power (\si{\micro\watt})')
        self.ax.set_ylabel(r'Total Received Power (\si{\micro\watt})')
        self.set_txlim(15, 130)
        self.ax.set_ylim(*self.ax.get_xlim())
        # Fig should be created with
        self.scatter = self.ax.scatter([], [])
        self.fit, = self.ax.plot([], [], ls=':')

        self.label = self.ax.annotate('No Data', (.47, .52), (.15, .7),
                                      xycoords='axes fraction',
                                      arrowprops=dict(facecolor='black',
                                                      width=0.1, headwidth=4,
                                                      headlength=6, shrink=.05))
    def update_emissivity(self, x, y, bg, e):
        self.scatter.set_offsets(np.c_[1e6*x, 1e6*y])

        fit_x = np.linspace(*self.ax.get_xlim(), 100)
        fit_y = e * fit_x + bg*1e6
        self.fit.set_xdata(fit_x)
        self.fit.set_ydata(fit_y)

        self.label.set_text(r' $ \SI{' f'{e:.3f}' r'}{} \sigma T^4 + \SI{' f'{1e6*bg:.1f}' r'}{\micro\watt} $')

        self.ax.set_ylim([1e6*bg+e*x for x in self.ax.get_xlim()])
        # self.label.set_position((fit_x[65], e * fit_x[65] + 1e6*bg))

def to_k(temperature):
    return 273.15 + temperature


def bandpass(temperatue):
    return np.interp(temperatue, BP_TEMP, BP_VAL)


def analyze_emissivity(measurements, plot_elements=None, output=None):
    if output is not None:
        logger.info('Writting File')
        with open(output, 'w', encoding='utf8') as f:
            f.write(','.join(measurements.keys())+'\n')
            for row in zip(*measurements.values()):
                f.write(','.join([f'{x:.3f}' for x in row])+'\n')
        logger.info('Writting done')

    # Regression
    
    temp = np.double(measurements['block_temp'])
    k = uw_pyrometer.pyrometer.RESPONSIVITY # G * sigma
    x = k * bandpass(temp)*to_k(temp)**4
    temp_tp = np.double(measurements['temp'])
    power = 1e-6 * np.double(measurements['power'])
    y = power + k * bandpass(temp_tp)*to_k(temp_tp)**4
    if len(measurements['block_temp']) >= 2:
        p, info = np.polynomial.polynomial.Polynomial.fit(x, y, 1, full=True)
        background, emissivity = p.convert().coef
    else:
        background = 1e-6 * measurements['power'][0]
        emissivity = 1.0
    # TODO: Calcualte Error

    # Plot scatter
    if plot_elements is not None:
        plot_elements.update_emissivity(x, y, background, emissivity)
        plt.show(block=False)
        plt.pause(5.0)

    return emissivity, background


async def set_and_wait(device, set_temp):
    device.sp(val=set_temp, save=False, index=2)
    await asyncio.sleep(3.0)
    device.restart()
    await asyncio.sleep(3.0)

    while abs(device.val() - set_temp) > T_DEADBAND:
        logger.debug('Not at temperature yet')
        await asyncio.sleep(20.0)


async def get_avg_temp(device, end_signal, callback_f):
    temp_samples = [device.val()]
    while not end_signal.is_set():
        # Don't check too often
        await asyncio.sleep(10.0)
        temp_samples.append(device.val())
    logger.debug('Done measuring temp')
    v = sum(temp_samples)/len(temp_samples)
    callback_f(v)
    return v


async def run_temps(tp_dev, temp_dev, temps, samples, interval, update_f=None):
    measurements = {x: [] for x in uw_pyrometer.pyrometer.MEAS_NAMES}
    measurements['block_temp'] = []
    measurements['tp_gain'] = []
    measurements['tr_gain'] = []

    def update_w_print(m):
        for k, v in m.items():
            measurements[k].append(v)

        temp = m['temp']
        power = m['power']
        print(f'{temp:.1f} C, {power:.1f} uW')
        
        if update_f is not None:
            update_f(measurements) # For plotting, or other updates
    
    tp_sampled = asyncio.Event()
    gains = None
    for t in temps:
        print('Temp:', t)
        await set_and_wait(temp_dev, t)
        logger.info('Setting gains')

        gains = await asyncio.to_thread(tp_dev.auto_gain, gains)
        measurements['tp_gain'].append(gains[0])
        measurements['tr_gain'].append(gains[1])
        tp_sampled.clear()

        sample_task = asyncio.create_task(tp_dev.sample(samples, interval, tp_sampled))
        measure_task = asyncio.create_task(get_avg_temp(temp_dev, tp_sampled, measurements['block_temp'].append))

        await tp_sampled.wait()
        await measure_task
        update_w_print(await sample_task)
        

    return measurements


def run(tp_dev, temp_dev, temps, samples, interval, plot=False, output=None):
    update_f = None
    vis = None
    if plot:
        logger.info('Setting up plots')
        plt.style.use(PLOT_STYLE)
        plt.ion()
        vis = EmissivityVis()
        plt.figure().canvas.manager.canvas.figure = vis
        plt.show(block=False)
        plt.pause(2.0)

    fig = None if plot else None # Matplotlib gui figure window
    update_f = lambda x: analyze_emissivity(x, vis, output)

    measurements = asyncio.run(run_temps(tp_dev, temp_dev, temps,
                                          samples, interval, update_f))
    analyze_emissivity(measurements, fig, output)


def test(heat_block):
    # Configure the controller
    # out2_config = {'enable_soak': False,
    #                 'enable_ramp': False,
    #                 'enable_autopid': False,
    #                 'time_prop': 0,
    #                 'enable_direct': 0}
    # heat_block.out2cnf(**out2_config)

    measured_temp = [heat_block.val()]
    if measured_temp[-1] is None:
        raise RuntimeError('No value is read.')
    print(f'Start Temp: {measured_temp[0]}')
    
    set_temp = 32.0
    heat_block.sp(val=set_temp, save=False, index=2)
    time.sleep(0.5)
    heat_block.restart()
    assert abs(heat_block.sp(index=2) - set_temp) < .1

    start = time.time()
    while measured_temp[-1] < set_temp:
        time.sleep(2.0)

        if (time.time() - start) > TEST_TIMEOUT:
            raise TimeoutError(f'Temp not reached in {TEST_TIMEOUT} s')

        measured_temp.append(heat_block.val())

        print('\b'*10 + f'Temp {measured_temp[-1]:5.1f}', end='', flush=True)

    print()
    heat_block.sp(val=20.0, save=False, index=2)
    time.sleep(0.5)
    heat_block.restart()
    assert abs(heat_block.sp(index=2) - 20.0) < T_DEADBAND
    heat_block.standby(1)

    return measured_temp
