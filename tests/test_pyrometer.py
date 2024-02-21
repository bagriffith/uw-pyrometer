import pty
import os
import pytest
from uw_pyrometer.pyrometer import PyrometerSerial


@pytest.fixture(scope="function")
def serial_simulator():
    mock_put, mock_get = pty.openpty()
    mock_serial = os.ttyname(mock_get)

    with os.fdopen(mock_put, "wb") as fd:
        def put(data):
            fd.write(data)
            fd.flush()

        yield mock_serial, put

def test_measurment(serial_simulator):
    mock_serial, put_data = serial_simulator
    device = PyrometerSerial(4, mock_serial)
    put_data(bytes([0x55, 0x04, 0x00, 0x0A, 0x1B, 0x2C, 0x3D, 0x4E, 0x5F]))
    reference, thermistor, thermopile = device.get_measurement()

    assert reference == 0x4E5F
    assert thermistor == 0x2C3D
    assert thermopile == 0x0A1B


def test_broken_measurment(serial_simulator):
    mock_serial, put_data = serial_simulator
    device = PyrometerSerial(4, mock_serial)
    put_data(bytes([0xAB, 0x12, 0x55, 0x04, 0x00, 0x0A, 0x1B, 0x2C, 0x3D, 0x4E, 0x5F, 0x34]))
    reference, thermistor, thermopile = device.get_measurement()

    assert reference == 0x4E5F
    assert thermistor == 0x2C3D
    assert thermopile == 0x0A1B

def test_read_temperature(serial_simulator):
    mock_serial, put_data = serial_simulator
    device = PyrometerSerial(4, mock_serial)
    device.set_gains(20, 4)
    temperature_zero = device.thermistor_temperature(3.298)
    temperature_525 = device.thermistor_temperature(device.adc_to_voltage(194.6))
    assert temperature_zero == pytest.approx(22.0, abs=.1)
    assert temperature_525 == pytest.approx(52.5, abs=.5)


def test_read_power(serial_simulator):
    mock_serial, put_data = serial_simulator
    device = PyrometerSerial(4, mock_serial)
    device.set_gains(24, 15)
    power_0 = device.thermopile_power(4.592)
    power_1 = device.thermopile_power(device.adc_to_voltage(619))

    assert power_0 == pytest.approx(100.0, .01)
    assert power_1 == pytest.approx(25.0, .01)
