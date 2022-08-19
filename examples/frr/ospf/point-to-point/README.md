OSPF Point-to-Point Network Simulation
======================================

This simulation demonstrates configuring point-to-point networks in FRRouting
through Munet.

The `ip ospf network` command must be used to configure a point-to-point
network. If not configured, the networks will default to broadcast behavior (see
multipoint simulation.)

```
                             10.0.2.0/24
     ----------------------------------------------------------
      |                      net2 (P2P)                      |
      |.1                                                  .3|
   +------+                   +------+                   +------+
   |      |    10.0.1.0/24    |      |    10.0.3.0/24    |      |
   |  r1  | ----------------- |  r2  | ----------------- |  r3  |
   |      |.1     net1      .2|      |.2  net3 (P2P)   .3|      |
   +------+                   +------+                   +------+


  \......................... area 0.0.0.0 ......................../
  
```