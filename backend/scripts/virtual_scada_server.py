"""A real local OPC-UA server with simulated nodes, per
CORRIX_REAL_DATA_BUILD_PLAN.md Step 24: the OPC-UA analog of the
MQTT path's virtual sensor publisher (Step 19). A genuine `asyncua`
server, real protocol, real client code needed to talk to it; the only
thing simulated is the value behind each node, exactly the same
relationship the MQTT path has to physical hardware.

One node per zone's gas concentration, ticked toward a target with the
same Ornstein-Uhlenbeck jitter app/simulation/gas_process.step already
uses for the synthetic scenarios and the MQTT virtual sensor publisher
(imported unmodified, per the build plan's own instruction not to
reimplement the OU math).

Run from backend/: python scripts/virtual_scada_server.py
Then read a node's value with any OPC-UA client, e.g.:
  python -c "
  import asyncio
  from asyncua import Client
  async def main():
      async with Client('opc.tcp://localhost:4840/freeopcua/server/') as client:
          var = await client.nodes.root.get_child(
              ['0:Objects', '2:CorrixVirtualPlant', '2:Z1_LEL']
          )
          print(await var.get_value())
  asyncio.run(main())
  "
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from asyncua import Server

from app.simulation.gas_process import step

ENDPOINT = "opc.tcp://0.0.0.0:4840/freeopcua/server/"
NAMESPACE_URI = "http://corrix.example/virtual-scada"
TICK_SECONDS = 1.5
CHANNEL_K = 0.3
CHANNEL_SIGMA = 0.15

# A handful of simulated zone/gas-type combinations and the target each
# ticks toward, standing in for a real plant historian's tag list.
ZONE_TARGETS = {
    "Z1_LEL": 8.0,
    "Z2_CO": 15.0,
    "Z3_H2S": 3.0,
}


async def _run_channel(var, target: float, rng: np.random.Generator) -> None:
    current = 0.0
    while True:
        await asyncio.sleep(TICK_SECONDS)
        current = step(current, CHANNEL_K, target, 0.0, CHANNEL_SIGMA, 1.0, rng)
        await var.write_value(round(float(current), 4))


async def main() -> None:
    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    idx = await server.register_namespace(NAMESPACE_URI)

    objects = server.get_objects_node()
    plant = await objects.add_object(idx, "CorrixVirtualPlant")

    tasks = []
    for tag_name, target in ZONE_TARGETS.items():
        var = await plant.add_variable(idx, tag_name, 0.0)
        await var.set_writable()
        rng = np.random.default_rng(abs(hash(tag_name)) % (2**32))
        tasks.append(asyncio.create_task(_run_channel(var, target, rng)))

    print(f"Virtual SCADA (OPC-UA) server running at {ENDPOINT}")
    print(f"Simulated tags: {', '.join(ZONE_TARGETS)}")

    async with server:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
