"""Simulated Modbus device; use run_simulators.py to run the complete system."""

import asyncio
import os
from contextlib import suppress
from datetime import datetime

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)

PORT = int(os.getenv("CHILLER_PORT", "5020"))
HOST = os.getenv("SIM_HOST", "127.0.0.1")
UPDATE_INTERVAL = float(os.getenv("SIM_INTERVAL", "1"))
UNIT_ID = 2

# Chiller Modbus register tables
store = ModbusDeviceContext(
    di=ModbusSequentialDataBlock(1, [0] * 10),
    co=ModbusSequentialDataBlock(1, [0] * 10),
    ir=ModbusSequentialDataBlock(1, [70, 120, 0] + [0] * 7),
    hr=ModbusSequentialDataBlock(1, [70] + [0] * 9),
)

context = ModbusServerContext(
    devices={UNIT_ID: store},
    single=False,
)

supply_temp = 7.0
return_temp = 12.0
previous_running = False
previous_low_flow = False


def update_chiller():
    """Read commands, advance chiller state and publish feedback."""
    global supply_temp, return_temp
    global previous_running, previous_low_flow

    # Read writable values from Modbus
    run_command = bool(store.getValues(1, 0, count=1)[0])
    setpoint_raw = store.getValues(3, 0, count=1)[0]
    setpoint = max(4.0, min(20.0, setpoint_raw / 10.0))

    if run_command:
        # Chiller is running
        supply_temp += (setpoint - supply_temp) * 0.20
        return_temp = supply_temp + 5.0
        flow = 45
        running = True
    else:
        # Chiller is stopped
        supply_temp += (20.0 - supply_temp) * 0.03
        return_temp += (supply_temp - return_temp) * 0.20
        flow = 0
        running = False

    low_flow_alarm = running and flow < 20

    # Update input registers
    store.setValues(
        4, 0,
        [round(supply_temp * 10),
         round(return_temp * 10),
         flow],
    )

    # Update discrete inputs
    store.setValues(
        2, 0,
        [int(running), int(low_flow_alarm)],
    )

    now = datetime.now().strftime("%H:%M:%S")

    print(
        f"[{now}] CHILLER | "
        f"Running={'ON' if running else 'OFF'} | "
        f"Supply={supply_temp:.1f} C | "
        f"Return={return_temp:.1f} C | "
        f"Flow={flow} L/min | "
        f"Setpoint={setpoint:.1f} C | "
        f"LowFlowAlarm={'ON' if low_flow_alarm else 'OFF'}",
        flush=True,
    )

    if running != previous_running:
        print(
            f">> Chiller {'STARTED' if running else 'STOPPED'}",
            flush=True,
        )
        previous_running = running

    if low_flow_alarm != previous_low_flow:
        print(
            f">> Low-flow alarm "
            f"{'ACTIVE' if low_flow_alarm else 'CLEARED'}",
            flush=True,
        )
        previous_low_flow = low_flow_alarm


async def simulation_loop():
    """Update the chiller once per configured interval."""
    while True:
        try:
            update_chiller()
        except Exception as e:
            print(f"ERROR: {e}", flush=True)

        await asyncio.sleep(UPDATE_INTERVAL)


async def main():
    """Start the standalone Modbus server and stop its background task on exit."""
    print(f"Starting Chiller simulator on port {PORT}")
    print(f"Unit ID: {UNIT_ID}")
    print("Press Ctrl+C to stop.")

    task = asyncio.create_task(simulation_loop())

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
        print("\nChiller simulator stopped.")
