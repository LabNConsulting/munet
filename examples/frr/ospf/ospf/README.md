FRR Simple OSPF Simulation
==========================

This simulation demonstrates a basic OSPF setup in FRRouting through Munet.

All configuration of the network topology must occur in `./munet.yaml` under the
`topology:` section. This includes defining routers and what networks they are
connected to. Interfaces can be individually specified if desired (see the
manual-interface simulation.)

All FRRouting clicmds are to be run directly in the Munet simulation, or a
predefined list of them can be automatically run through configuring the
`./ROUTER_NAME/etc.frr/frr.conf` file. In the case of this simulation, all
routers are named after r1, r2, r3, ...

In this simulation, all interfaces are configured collectively to run OSPF
through the `ospf network area` clicmd. It is also possible to configure each
interface individually to run OSPF through the `ip ospf area` clicmd. Examples
of this usage can be found in other simulations.

```
                             10.0.2.0/24
     ----------------------------------------------------------
      |                         net2                         |
      |.1                                                  .3|
   +------+                   +------+                   +------+
   |      |    10.0.1.0/24    |      |    10.0.3.0/24    |      |
   |  r1  | ----------------- |  r2  | ----------------- |  r3  |
   |      |.1     net1      .2|      |.2     net3      .3|      |
   +------+                   +------+                   +------+


  \......................... area 0.0.0.0 ......................../
  
```
