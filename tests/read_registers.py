"""Live TCP smoke check. Start src/run_simulators.py first. Writes and restores RPM."""
import os
from pymodbus.client import ModbusTcpClient


def check(response):
    """Reject protocol errors before inspecting response data."""
    if response.isError():
        raise RuntimeError(str(response))
    return response


def main():
    """Read every unit over TCP and verify a reversible RPM command."""
    host = os.getenv('SIM_HOST', '127.0.0.1')
    for variable, default, units in [('BIOREACTOR1_PORT', 5020, [1, 2]),
                                      ('BIOREACTOR2_PORT', 5022, [3])]:
        with ModbusTcpClient(host, port=int(os.getenv(variable, str(default))), timeout=3) as client:
            for unit in units:
                count = 3 if unit == 2 else 2
                values = check(client.read_input_registers(0, count=count, device_id=unit)).registers
                check(client.read_coils(0, count=1, device_id=unit))
                check(client.read_discrete_inputs(0, count=2 if unit == 2 else 1, device_id=unit))
                print(f'PASS unit={unit}, input registers={values}, temperature={values[0]/10:.1f} C')
                if unit != 2:
                    original = check(client.read_holding_registers(0, count=1, device_id=unit)).registers[0]
                    try:
                        check(client.write_register(0, 150, device_id=unit))
                        actual = check(client.read_holding_registers(0, count=1, device_id=unit)).registers[0]
                        if actual != 150:
                            raise AssertionError(f'RPM readback: {actual}')
                        print(f'PASS unit={unit}, RPM write/readback=150')
                    finally:
                        check(client.write_register(0, original, device_id=unit))


if __name__ == '__main__':
    main()
