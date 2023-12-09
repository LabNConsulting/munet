PIM Assert Simulation
=====================

This simulation demonstrates the PIM assert process through an example topology
in FRRouting through Munet. rtr2 and rtr3 will share metrics following the PIM
assert process and determine a winner. The other router gets pruned, therefore
avoiding duplicate traffic. In this case, rtr2 is configured to have a lower
metric than rtr3, and therefore will be selected as the winner. The network also
utilizes OSPF to populate all routing tables.

```

   +------+                                                  +------+
   | src- |  <-- Source of 224.1.1.1                         | rec- |
   | rtr1 |                                                  | rtr4 |
   |      |                        (*, 224.1.1.1) Member --> |      |
   +--+---+                                                  +--+---+
      |.10                               Metric: 5              |.10
      |                         +------+ |                      |
      | 11.0.1.0/24             |      | V                      | 11.0.4.0/24
      | local-rtr1          /---+ rtr2 +---\                    | local-rtr4
      |                    /  .2|      |.2  \                   |
      |.1                  |    +------+    |                   |.4
   +--+---+                |                |                +--+---+
   |      |   10.0.1.0/24  |                |  10.0.2.0/24   |      |
   | rtr1 +----------------|                |----------------+ rtr4 |
   |      |.1    net1      |    +------+    |     net2     .4|      |
   +------+                \  .3|      |.3  /                +------+
                            \---+ rtr3 +---/ 
                                |      | ^
                                +------+ |
                                         Metric: 10
```
