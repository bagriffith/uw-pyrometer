import time
import asyncio
import logging
from uw_pyrometer import pyrometer

T_DEADBAND = 1.0
TEST_TIMEOUT = 600  # Seconds

logger = logging.getLogger(__name__)

# TODO: Avg block temp sampling func


def analyze_emissivity(measurements, fig=None, output=None):
    print(measurements)

    if output is not None:
        with open(output, 'w', encoding='utf8') as f:
            f.write(','.join(measurements.keys())+'\n')
            for row in zip(*measurements.values()):
                f.write(','.join([f'{x:.1f}' for x in row])+'\n')   

    # Regression

    # Calculate emissivity and error
    emissivity = 0.0
    background = 0.0

    # Plot scatter

    return emissivity, background



async def set_and_wait(device, set_temp):
    device.sp(val=set_temp, save=False, index=2)
    await asyncio.sleep(0.2)
    device.restart()
    await asyncio.sleep(0.2)

    while device.val() - set_temp > 0.1:
        await asyncio.sleep(2.0)


async def get_avg_temp(device, end_signal, callback_f):
    temp_samples = []
    while not end_signal.is_set():
        temp_samples.append(device.val())
        await asyncio.sleep(2.0)
    v = sum(temp_samples)/len(temp_samples)
    callback_f(v)
    return v


async def run_temps(tp_dev, temp_dev, temps, samples, interval, update_f=None):
    measurements = {x: [] for x in pyrometer.MEAS_NAMES}
    measurements['block_temp'] = []

    def update_w_print(m):
        for k, v in m.items():
            measurements[k].append(v)

        temp = m['temp']
        power = m['power']
        print(f'{temp:.1f} C, {power:.1f} uW')
        
        if update_f is not None:
            update_f(m) # For plotting, or other updates
    
    tp_sampled = asyncio.Event()
    sample_task = asyncio.sleep(0)
    measure_task = asyncio.sleep(0)
    gains = None
    for t in temps:
        print('Temp:', t)
        temp_set = set_and_wait(temp_dev, t)
        await temp_set
        gains = await asyncio.to_thread(tp_dev.autogain(gains))

        await sample_task
        await measure_task
        tp_sampled.clear()

        sample_task = asyncio.create_task(tp_dev.sample(samples, interval, tp_sampled, update_w_print))
        measure_task = asyncio.create_task(get_avg_temp(temp_dev, tp_sampled, measurements['block_temp'].append))

        await asyncio.wait_for(tp_sampled.wait(), 10.0)

    await sample_task
    await measure_task
    return measurements


def run(tp_dev, temp_dev, temps, samples, interval, plot=False, output=None):
    update_f = None
    if plot:
        raise NotImplementedError('Live plot not finished')
    fig = None if plot else None # Matplotlib gui figure window
    update_f = lambda x: analyze_emissivity(x, fig, output)

    measurements  = asyncio.run(run_temps(tp_dev, temp_dev, temps,
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

    heat_block.sp(val=20.0, save=False, index=2)
    time.sleep(0.5)
    heat_block.restart()
    assert abs(heat_block.sp(index=2) - 20.0) < T_DEADBAND
    heat_block.standby(1)

    return measured_temp
