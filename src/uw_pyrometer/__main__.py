import sys

if __name__ == "__main__":
    from uw_pyromter.cli import uw_pyrometer, measure, gain

    uw_pyrometer.add_command(measure)
    uw_pyrometer.add_command(gain)

    sys.exit(uw_pyrometer())
