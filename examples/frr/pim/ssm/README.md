Source-Specific Multicast (SSM) Simulation
==========================================

This simulation demonstrates the configuration of source-speficic Multicast via
PIM-SSM and IGMP in FRRouting through Munet. The network also utilizes OSPF to
populate all all routing tables.

```

   +------+                                              +------+
   | src- | <-- Source of 232.1.1.1                      | rec- |
   | rtr1 |                                              | rtr3 |
   |      |           (11.0.1.10, 232.1.1.1) Member -->  |      |
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
                              |      |
                              +--+---+
   +------+                  /.2 |.2  \.2                +------+
   |      |   10.0.5.0/24   /    |     \   10.0.3.0/24   |      |
   | rtr6 + ---------------/     |      \----------------+ rtr4 |
   |      |.6    net5            |            net3     .4|      |
   +--+---+                      |                       +--+---+
      |.6                        | 10.0.5.0/24              |.4
      |                          | net4                     |
      | 11.0.6.0/24              |                          | 11.0.4.0/24
      | local-rtr6               |.5                        | local-rtr4
      |                       +--+---+                      |
      |.10                    |      |                      |.10
   +--+---+                   | rtr5 |                   +--+---+
   | src- |                   |      |                   | rec- |
   | rtr6 |                   +------+                   | rtr4 |
   |      | <--                                          |      |
   +------+    \       (11.0.6.10, 232.1.1.1) Member --> +------+
                \
                 -- Source of 232.1.1.1

```
