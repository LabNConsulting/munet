Router Priority OSPF Simulation
===============================

This simulation demonstrates how to set OSPF router priority through an
FRRouting simulation in Munet.

In this simulation, there are three separate routers connected to the same
network. since r2's router priority is set at 99 using the `ip ospf priority`
clicmd, however, r2 will always win the Designated Router election and become
DR. Normally the tie-break would elect r3.

```
                  net1
 ----------------------------
   |          | PRI:99    |
  +--+       +--+       +--+
  |r1|       |r2|       |r3|
  +--+       +--+       +--+
               
```
