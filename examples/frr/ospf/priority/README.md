Router Priority OSPF Simulation
===============================

This simulation demonstrates how to set OSPF router priority through an
FRRouting simulation in Munet.

In this simulation, there are four separate routers connected to the same
network. since r4's router priority is set at 99 using the `ip ospf priority`
clicmd, however, r4 will always win the Designated Router election and become
DR.