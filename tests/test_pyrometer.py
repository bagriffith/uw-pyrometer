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

    assert reference == 0x0A1B
    assert thermistor == 0x2C3D
    assert thermopile == 0x4E5F


def test_broken_measurment(serial_simulator):
    mock_serial, put_data = serial_simulator
    device = PyrometerSerial(4, mock_serial)
    put_data(bytes([0xAB, 0x12, 0x55, 0x04, 0x00, 0x0A, 0x1B, 0x2C, 0x3D, 0x4E, 0x5F, 0x34]))
    reference, thermistor, thermopile = device.get_measurement()

    assert reference == 0x0A1B
    assert thermistor == 0x2C3D
    assert thermopile == 0x4E5F

