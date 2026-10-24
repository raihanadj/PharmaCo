# ISA-95-inspired namespace
| Segment | Example | Meaning |
|---|---|---|
| Enterprise | PharmaCo | Fictional enterprise |
| Site | Dublin | Site |
| Area | Upstream / Utilities | Process area |
| Line | Line1 | Local grouping |
| Asset | Bioreactor1 / Bioreactor2 / Chiller1 | Equipment |

This is a learning hierarchy inspired by ISA-95, not a certification of compliance. Each asset topic carries a JSON object of its measurements. Confirm exact payload field names from the HighByte export when available. `PharmaCo/Dublin/#` selects all descendant topics.
