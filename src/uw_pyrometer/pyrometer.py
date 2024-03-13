import logging
from importlib import resources as impresources
import serial
import yaml
import numpy as np
import uw_pyrometer

logger = logging.getLogger(__name__)

UNITS = {'Temperature': 'C',
         'Power': 'uW',
         'Voltage': 'V'}

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
        with open(path) as f:
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

    def send(self, message, broadcast=False):
        header = bytes([self.SYNC_WORD, 0xFF if broadcast else self.id])
        self.serial.write(header)
        logger.debug('Writing %s', [f'0x{x:02X}' for x in header])
        self.serial.write(message)
        logger.debug('Writing %s', [f'0x{x:02X}' for x in message])

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
        self.send([self.CMD_SET_POT, thermopile_gain, thermistor_gain], broadcast)
        self.pot_thermopile = thermopile_gain
        self.pot_thermistor = thermistor_gain

    def get_measurement(self, broadcast=False):
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
