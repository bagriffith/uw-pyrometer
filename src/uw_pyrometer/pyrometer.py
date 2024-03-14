import logging
import asyncio
import time
from importlib import resources as impresources
import serial
import yaml
import numpy as np
import uw_pyrometer

logger = logging.getLogger(__name__)

MEAS_NAMES = ['tr_v', 'temp', 'ref_v', 'tp_v', 'power']

DATA_DIR = impresources.files(uw_pyrometer) / 'data/'
DEFAULT_CALIBRATION = DATA_DIR / 'default_calibration.yaml'


class PyrometerCalibration:
    __spec__ = ('thermistor_slope', 'thermistor_zero')
    ROOM_TEMP = 22.0 # Deg C

    def __init__(self, thermistor_zero, thermopile_resp):
        self.r_zero = thermistor_zero
        self.tp_resp = thermopile_resp

    @staticmethod
    def from_yaml(path):
        # process yaml
        with open(path, encoding='utf8') as f:
            calibration_yaml = yaml.safe_load(f)
        thermistor_zero = calibration_yaml['thermistor']['room_temp']
        thermopile_resp = calibration_yaml['thermopile']['responsivity']

        return PyrometerCalibration(thermistor_zero, thermopile_resp)


class PyrometerSerial:
    """Interface a UW pyrometer board."""
    __spec__ = ('id', 'serial', 'pot_thermopile', 'pot_thermistor', 'calibration')
    serial_kw_args = {'baudrate': 9600,
                      'bytesize': 8,
                      'parity': 'N',
                      'stopbits': 1,
                      'timeout': 4.0}
    SYNC_WORD = 0x55
    CMD_SET_POT = 0x01
    CMD_REPORT = 0x00
    THERMISTOR_CURVE = np.genfromtxt(DATA_DIR / 'dc_4007.csv', delimiter=",", skip_header=1)
    # Normalize to room temperature
    THERMISTOR_CURVE[:, 1] /= np.interp(PyrometerCalibration.ROOM_TEMP,
                                        THERMISTOR_CURVE[:, 0],
                                        THERMISTOR_CURVE[:, 1])

    def __init__(self, device_id, address, calibration=None):
        if not 0 <= device_id < 255:
            raise ValueError('Device id must be one byte. '
                             '0xFF is reserved for broadcast.')

        self.id = device_id
        self.serial = serial.Serial(address, **self.serial_kw_args)
        self.pot_thermopile = None
        self.pot_thermistor = None
        if calibration is None:
            self.calibration = PyrometerCalibration.from_yaml(DEFAULT_CALIBRATION)
        else:
            self.calibration = calibration

    def __enter__(self):
        self.open()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def open(self):
        if self.serial is None:
            logger.debug('Opening port')
            self.serial.open()

    def close(self):
        logger.debug('Closing port')
        self.serial.close()

    def clear(self):
        self.serial.flush()
        while self.serial.in_waiting:
            self.read()

    def send(self, message, broadcast=False):
        header = bytes([self.SYNC_WORD, 0xFF if broadcast else self.id])
        self.serial.write(header)
        logger.debug('Writing %s', [f'0x{x:02X}' for x in header])
        self.serial.write(message)
        logger.debug('Writing %s', [f'0x{x:02X}' for x in message])
        self.serial.flush()

    def read(self, packet_size=7):
        pre_data = self.serial.read_until(bytes([self.SYNC_WORD, self.id]))
        logger.debug('Read %s', [f'0x{x:02X}' for x in pre_data])
        packet = self.serial.read(packet_size)
        logger.debug('Read %s', [f'0x{x:02X}' for x in packet])
        if len(packet) != packet_size:
            # Assume the board has power cycled
            self.pot_thermopile = None
            self.pot_thermistor = None
            raise TimeoutError('Packet read timed out.')
        return packet

    def set_gains(self, thermopile_gain, thermistor_gain, broadcast=False):
        if not (0 <= thermopile_gain < 256 and 0 <= thermistor_gain < 256):
            raise ValueError('Gains must be single byte.')
        self.clear()
        self.send([self.CMD_SET_POT, thermopile_gain, thermistor_gain], broadcast)
        time.sleep(10.0) # Gain changes take a while to show up
        self.pot_thermopile = thermopile_gain
        self.pot_thermistor = thermistor_gain

    def get_measurement(self, broadcast=False):
        self.clear()
        self.send(bytes([self.CMD_REPORT]), broadcast)
        packet = self.read(7)

        if packet[0] != self.CMD_REPORT:
            logger.warning('Response echoed command %s instead of %s',
                           hex(packet[0]), hex(self.CMD_REPORT))

        thermopile = int.from_bytes(packet[1:3], 'big')
        thermistor = int.from_bytes(packet[3:5], 'big')
        reference = int.from_bytes(packet[5:7], 'big')
        logger.debug('Measured: ref %s; tr %s; tp %s',
                     reference, thermistor, thermopile)
        for measurement, name in zip([thermopile, thermistor, reference],
                                     ['Thermopile', 'Thermistor', 'Reference']):
            if not 16 < measurement < 1008:
                logger.warning('Measurement %s is close to ADC limits.', name)

        return reference, thermistor, thermopile

    def thermistor_temperature(self, thermistor_voltage):
        if self.pot_thermistor is None:
            raise RuntimeError('Potentiometer not set.')

        pre_amp_voltage = self.pot_thermistor * thermistor_voltage / 255
        resistance = 2.2e6 / (5.0/pre_amp_voltage - 1.) # R_T / R4

        logger.debug('Resistance %s', resistance)
        if not (self.THERMISTOR_CURVE[-1, 1] < resistance/self.calibration.r_zero < self.THERMISTOR_CURVE[0, 1]):
            logger.warning('Thermistor temperature is out of calibration range')

        temperature = np.interp(resistance/self.calibration.r_zero,
                                self.THERMISTOR_CURVE[::-1, 1],
                                self.THERMISTOR_CURVE[::-1, 0])
        # temperature = (resistance / self.calibration.r_zero - 1) / self.calibration.r_slope
        return temperature

    def thermopile_power(self, thermopile_voltage, reference_voltage=2.5):
        pre_amp_voltage = self.thermopile_voltage(thermopile_voltage, reference_voltage)
        power = pre_amp_voltage / self.calibration.tp_resp
        return power

    def thermopile_voltage(self, thermopile_voltage, reference_voltage=2.5):
        if self.pot_thermopile is None:
            raise RuntimeError('Potentiometer not set.')
        return self.pot_thermopile * (thermopile_voltage - reference_voltage) / (255 * 51.)

    @staticmethod
    def adc_to_voltage(adc_value):
        return (adc_value * 5)/1024.

    def auto_gain(self, start=None):
        tp_gain, tr_gain = (20, 20) if start is None else start

        min_error_tp, min_error_tr = 1024, 1024

        trial_tp_gain = tp_gain
        trial_tr_gain = tr_gain

        for gain_n in range(32):
            self.set_gains(trial_tp_gain, trial_tr_gain)
            _, tr, tp = self.get_measurement()

            trial_error_tp = abs(abs(tp-512) - 256)
            trial_error_tr = abs(tr - 512)

            if trial_error_tp < min_error_tp:
                min_error_tp = trial_error_tp
                tp_gain = trial_tp_gain

            if trial_error_tr < min_error_tr:
                min_error_tr = trial_error_tr
                tr_gain = trial_tr_gain

            if max(min_error_tp, min_error_tr) < 64:
                logger.info('Sufficient value found after %s guesses', gain_n+1)
                logger.info('Gains are (%s,%s)', tp_gain, tr_gain)
                break

            # Guess a better value
            if tp == 1024:
                trial_tp_gain = trial_tp_gain*2
            else:
                guess = (abs(tp-512) * trial_tp_gain) // 256
                if guess == trial_tp_gain:
                    trial_tp_gain += -1 if abs(tp-512) < 255 else 1
                else:
                    trial_tp_gain = guess
                    

            if tr == 1024:
                trial_tr_gain = trial_tr_gain*2
            else:
                guess = (tr * trial_tr_gain) // 512
                if guess == trial_tr_gain:
                    trial_tr_gain += -1 if tr < 255 else 1
                else:
                    trial_tr_gain = guess

            trial_tp_gain = max(min(trial_tp_gain, 255), 1)
            trial_tr_gain = max(min(trial_tr_gain, 255), 1)

            if (trial_tp_gain == tp_gain) and (trial_tr_gain == tr_gain):
                logger.info('Most acceptable value found after %s guesses', gain_n+1)
                logger.info('Gains are (%s,%s)', tp_gain, tr_gain)
                break

            logger.debug('Try: (%s, %s)', trial_tp_gain, trial_tr_gain)
        else:
            logger.warning('Correct gain not found.')

        self.set_gains(tp_gain, tr_gain)

        return tp_gain, tr_gain

    async def sample(self, samples, interval, complete=None, updater_f=None):
        if complete is None:
            complete = asyncio.Event()

        sample_history = {x: [] for x in MEAS_NAMES}

        samples_taken = 0
        while not complete.is_set():
            try:
                ref, tr, tp = await asyncio.to_thread(self.get_measurement)
            except TimeoutError:
                logger.warning('Read timed out')
                continue

            # Increment measurement counter
            samples_taken += 1
            if samples_taken >= samples:
                complete.set() # Done measuring

            tr_v = self.adc_to_voltage(tr)
            sample_history['tr_v'].append(tr_v)
            temp = self.thermistor_temperature(tr_v)
            sample_history['temp'].append(temp)

            tp_v = self.adc_to_voltage(tp)
            sample_history['tp_v'].append(tp_v)
            ref_v = self.adc_to_voltage(ref)
            sample_history['ref_v'].append(ref_v)

            power = self.thermopile_power(tp_v, ref_v)
            sample_history['power'].append(power)

            if updater_f is not None:
                # Call an updater for a progress indicator
                await asyncio.to_thread(updater_f, sample_history)

            if not complete.is_set():
                await asyncio.sleep(interval)

        return {k: sum(v)/len(v) for k, v in sample_history.items()}
