# Register design
See the complete map in the README. Unit IDs: Bioreactor1=1 (5020), Chiller1=2 (5020), Bioreactor2=3 (5022). Function codes: 04=input registers, 03=holding registers, 01=coils, 02=discrete inputs. Tables are independent: offset 0 in each table is a different value.

The pymodbus 3.12.0 device context internally adds one to public offsets. Data blocks therefore start at 1 while calls use 0. This convention was checked over TCP; do not change block starts without repeating the live tests.

Temperature wanders within 34–40 °C, pH within 6.5–7.5. Heater is ON strictly below 36.5 °C; alarm is ON strictly above 38 °C. Thresholds use the unrounded process value, so a displayed boundary value may have a flag set due to rounding.

Chiller supply approaches a command clamped to 4–20 °C while running, with flow 45 L/min and return=supply+5 °C. Stopped supply approaches 20 °C and flow is zero. Clamping affects the simulation's effective target; the holding register retains the written raw command. Low-flow is running AND flow<20, which is unreachable under the current fixed-flow model.

Heater coil is calculated every update; external writes are overwritten. RPM is writable and preserved. Chiller run command remains writable. No process interaction links chiller and bioreactor temperatures.
