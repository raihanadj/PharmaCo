"""Run Bioreactor1 and Chiller1 on one server, and Bioreactor2 on another."""
import asyncio
from contextlib import suppress
from pymodbus.datastore import ModbusServerContext
from pymodbus.server import ModbusTcpServer
import bioreactor_sim as bio1
import bioreactor2_sim as bio2
import chiller_sim as chiller


async def main():
    """Share port 5020 across two units instead of binding it twice."""
    if bio1.PORT != chiller.PORT:
        raise ValueError('Combined mode requires BIOREACTOR1_PORT and CHILLER_PORT to match.')
    if bio1.PORT == bio2.PORT:
        raise ValueError('BIOREACTOR2_PORT must differ from the shared device port.')
    shared = ModbusServerContext(devices={bio1.UNIT_ID: bio1.store,
                                         chiller.UNIT_ID: chiller.store}, single=False)
    servers = [ModbusTcpServer(shared, address=(bio1.HOST, bio1.PORT)),
               ModbusTcpServer(bio2.context, address=(bio2.HOST, bio2.PORT))]
    tasks = []
    try:
        # Bind both ports before starting process updates.
        for server in servers:
            await server.serve_forever(background=True)
        print(f'Ready: Bioreactor1 unit 1 + Chiller1 unit 2 at {bio1.HOST}:{bio1.PORT}; '
              f'Bioreactor2 unit 3 at {bio2.HOST}:{bio2.PORT}', flush=True)
        tasks = [asyncio.create_task(bio1.process_loop()),
                 asyncio.create_task(chiller.simulation_loop()),
                 asyncio.create_task(bio2.process_loop())]
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        for server in servers:
            await server.shutdown()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nStopped.')
