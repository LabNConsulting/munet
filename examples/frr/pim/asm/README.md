Any Source Multicast (ASM) Simulation
=====================================

This simulation demonstrates the configuration of ASM Multicast via PIM and IGMP
in FRRouting through Munet. The network also utilizes OSPF to populate all
routing tables.

```

   +------+                                              +------+
   | src- |  <-- Source of 224.1.1.1                     | rec- |
   | rtr1 |                                              | rtr3 |
   |      |                    (*, 224.1.1.1) Member --> |      |
   +--+---+                                              +--+---+
      |.10                                                  |.10
      |                                                     |
      | 11.0.1.0/24                                         | 11.0.3.0/24
      | local-rtr1                                          | local-rtr3
      |                                                     |
      |.1                                                   |.3
   +--+---+                                              +--+---+
   |      |   10.0.1.0/24                  10.0.2.0/24   |      |
   | rtr1 +----------------\            /----------------+ rtr3 |
   |      |.1    net1       \          /      net2     .3|      |
   +------+                  \.2      /.2                +------+
                              +------+
                              |      |
                              | rtr2 |
                              | (RP) |
                              +--+---+
                                 |.2  \.2                +------+
                                 |     \   10.0.3.0/24   |      |
                                 |      \----------------+ rtr4 |
       No Multicast packets! --> |            net3     .4|      |
                                 |                       +--+---+
                                 | 10.0.5.0/24              |.4
                                 | net4                     |
                                 |                          | 11.0.4.0/24
                                 |.5                        | local-rtr4
                              +--+---+                      |
                              |      |                      |.10
                              | rtr5 |                   +--+---+
                              |      |                   | rec- |
                              +------+                   | rtr4 |
                                                         |      |
                               (*, 224.1.1.1) Member --> +------+

```
