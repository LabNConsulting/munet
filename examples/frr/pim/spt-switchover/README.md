PIM Shortest Path Tree Switchover Simulation
============================================

This simulation demonstrates the configuration of Multicast via PIM and IGMP in
FRRouting through Munet. Due to the network's structure, a Shortest Path Tree
Switchover (SPT Switchover) will occur. The network also utilizes OSPF to
populate all routing tables.

```
   +------+                                              +------+
   | src- | <-- Source of 224.1.1.1                      | rec- |
   | rtr1 |                                              | rtr5 |
   |      |                   (*, 224.1.1.1) Member -->  |      |
   +--+---+                                              +--+---+
      |.10                                                  |.10
      |                                                     |
      | 11.0.1.0/24                                         | 11.0.5.0/24
      | local-rtr1                                          | local-rtr5
      |                                                     |
      |.1                                                   |.5
   +--+---+                   +------+                   +--+---+
   |      |    10.0.6.0/24    |      |    10.0.5.0/24    |      |
   | rtr1 +-------------------+ rtr6 +-------------------+ rtr5 |
   |      |.1     net6      .6|      |.6     net5      .5|      |
   +--+---+                   +------+                   +--+---+
      |.1                                                   |.5
      |                                                     |
      | 10.0.1.0/24                                         | 10.0.4.0/24
      | net1            Route through RP is pruned!         | net4
      |                          |                          |
      |.2                        V                          |.4
   +--+---+                   +------+                   +--+---+
   |      |    10.0.2.0/24    |      |    10.0.3.0/24    |      |
   | rtr2 +-------------------+ rtr3 +-------------------+ rtr4 |
   |      |.2     net2      .3| (RP) |.3     net3      .4|      |
   +------+                   +------+                   +------+

```