"""Simulated Modbus device; use run_simulators.py to run the complete system."""
import asyncio
import os
from contextlib import suppress
import random
from datetime import datetime

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)

PORT = int(os.getenv("BIOREACTOR1_PORT", "5020"))
HOST = os.getenv("SIM_HOST", "127.0.0.1")
UPDATE_INTERVAL = float(os.getenv("SIM_INTERVAL", "1"))
UNIT_ID = 1

# Modbus data addresses are zero-based.
# Temperature and pH are stored as scaled integers.
store = ModbusDeviceContext(
        di=ModbusSequentialDataBlock(1, [0] * 10),
        co=ModbusSequentialDataBlock(1, [0] * 10),
        ir=ModbusSequentialDataBlock(1, [370, 700] + [0] * 8),
        hr=ModbusSequentialDataBlock(1, [100] + [0] * 9),
)

context = ModbusServerContext(devices={UNIT_ID: store}, single=False)

temperature = 37.0
ph = 7.0
previous_heater = None
previous_alarm = None


def update_registers():
    """Advance simulated temperature/pH and publish register values."""
    global temperature, ph, previous_heater, previous_alarm

    # Simulate small process fluctuations.
    temperature += random.uniform(-0.08, 0.08)
    temperature = max(34.0, min(40.0, temperature))

    ph += random.uniform(-0.015, 0.015)
    ph = max(6.5, min(7.5, ph))

    heater = temperature < 36.5
    alarm = temperature > 38.0

    # Input registers: address 0 = Temperature, address 1 = pH.
    store.setValues(4, 0, [round(temperature * 10), round(ph * 100)])

    # Coil: address 0 = HeaterOn.
    store.setValues(1, 0, [int(heater)])

    # Discrete input: address 0 = HighTempAlarm.
    store.setValues(2, 0, [int(alarm)])

    now = datetime.now().strftime("%H:%M:%S")
    print(
        f"[{now}] Temperature={temperature:.1f} C "
        f"(raw={round(temperature * 10)}, address=30001) | "
        f"pH={ph:.2f} (raw={round(ph * 100)}, address=30002) | "
        f"Heater={'ON' if heater else 'OFF'} | "
        f"HighTempAlarm={'ON' if alarm else 'OFF'} | "
        f"RPM Setpoint={store.getValues(3, 0, count=1)[0]}",
        flush=True,
    )

    if heater != previous_heater:
        print(f">> Heater changed to {'ON' if heater else 'OFF'}", flush=True)
        previous_heater = heater

    if alarm != previous_alarm:
        print(f">> High-temperature alarm {'ACTIVE' if alarm else 'CLEARED'}", flush=True)
        previous_alarm = alarm


async def process_loop():
    """Update the process once per configured interval."""
    while True:
        try:
            update_registers()
        except Exception as e:
            print(
                f"SIMULATION LOOP ERROR: {type(e).__name__}: {e}",
                flush=True,
            )
        await asyncio.sleep(UPDATE_INTERVAL)


async def main():
    """Start the standalone Modbus server and stop its background task on exit."""
    print(f"Starting bioreactor simulator on port {PORT}, Unit ID {UNIT_ID}")
    print("Press Ctrl+C to stop.")

    task = asyncio.create_task(process_loop())

    try:
        await StartAsyncTcpServer(
            context=context,
            address=(HOST, PORT),
        )
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
