import logging
import serial

logger = logging.getLogger(__name__)


class PyrometerSerial:
    """Interface a UW pyrometer board."""
    __spec__ = ('id', 'serial')
    serial_kw_args = {'baudrate': 9600,
                      'bytesize': 8,
                      'parity': 'N',
                      'stopbits': 1,
                      'timeout': 4.0}
    SYNC_WORD = 0x55
    CMD_SET_POT = 0x01
    CMD_REPORT = 0x00

    def __init__(self, device_id, address) -> None:
        if not 0 <= device_id < 255:
            raise ValueError('Device id must be one byte. '
                             '0xFF is reserved for broadcast.')

        self.id = device_id
        self.serial = serial.Serial(address, **self.serial_kw_args)

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
            raise TimeoutError('Packet read timed out.')
        return packet

    def set_gains(self, thermopile_gain, thermistor_gain, broadcast=False):
        if not (0 <= thermopile_gain < 256 and 0 <= thermistor_gain < 256):
            raise ValueError('Gains must be single byte.')
        self.send([self.CMD_SET_POT, thermopile_gain, thermistor_gain], broadcast)
        # Should I look for a response?

    def get_measurement(self, convert=False, broadcast=False):
        self.send(bytes([self.CMD_REPORT]), broadcast)
        packet = self.read(7)

        if packet[0] != self.CMD_REPORT:
            logger.warning('Response echoed command %s instead of %s',
                           hex(packet[0]), hex(self.CMD_REPORT))

        reference = int.from_bytes(packet[1:3], 'big')
        thermistor = int.from_bytes(packet[3:5], 'big')
        thermopile = int.from_bytes(packet[5:7], 'big')
        logger.debug('Measured: ref %s; tr %s; tp %s',
                     reference, thermistor, thermopile)
        if convert:
            return self.adc_to_voltage(reference), \
                    self.adc_to_voltage(thermistor), \
                    self.adc_to_voltage(thermopile)
        else:
            return reference, thermistor, thermopile

    @staticmethod
    def adc_to_voltage(adc_value):
        return (adc_value * 5)/1024.
