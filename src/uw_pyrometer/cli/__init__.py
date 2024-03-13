import click
import yaml
from uw_pyrometer import pyrometer


class Calibration(click.Path):
    def convert(self, value, param, ctx):
        path = super().convert(value, param, ctx)
        try:
            return pyrometer.PyrometerCalibration.from_yaml(path)
        except yaml.YAMLError as exp:
            self.fail(f'Invalid yaml {exp}', param, ctx)
