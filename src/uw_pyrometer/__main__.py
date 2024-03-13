import sys

if __name__ == "__main__":
    from uw_pyromter.cli.instrument import uw_pyrometer, measure, gain, measure_physical

    uw_pyrometer.add_command(measure)
    uw_pyrometer.add_command(gain)
    uw_pyrometer.add_command(measure_physical)

    sys.exit(uw_pyrometer())
