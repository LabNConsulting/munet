OSPF Point-to-Point Network Simulation
======================================

This simulation demonstrates creating point-to-point munet connections
and configuring point-to-point networks in FRRouting OSPF.

The `ip ospf network` command must be used to configure a point-to-point
network. If not configured, the networks will default to broadcast behavior (see
multipoint simulation.)

```
                            10.254.1.2/30
      .------------------------------------------------------.
      |                        r1-r3                         |
      |.2                                                  .3|
   +------+                   +------+                   +------+
   |      |   10.254.1.0/30   |      |   10.254.2.0/30   |      |
   |  r1  | ----------------- |  r2  | ----------------- |  r3  |
   |      |.0     r1-r2     .1|      |.0     r2-r3     .1|      |
   +------+                   +------+                   +------+


  \......................... area 0.0.0.0 ......................../

```
