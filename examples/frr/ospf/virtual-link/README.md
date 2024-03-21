OSPF Virtual-Link Simulation
============================

This simulation demonstrates configuring a virtual-link in FRRouting
through Munet.

In this simulation, area 2.2.2.2 isn't directly connected to the backbone.
Instead, it is directly connected to area 1.1.1.1. To fix this and connect area
2.2.2.2 to the backbone, the `area virtual-link` clicmd must be used on both
of area 1.1.1.1's ABRs (r2 and r4.)

```
  /'''''''''''''''''''''''' area 1.1.1.1 '''''''''''''''''''''''''\
 
   +------+                   +------+                   +------+
   |      |    10.0.2.0/24    |      |    10.0.3.0/24    |      |
   |  r2  | ----------------- |  r3  | ----------------- |  r4  |
   |      |.2     net2      .3|      |.3     net3      .4|      |
   +------+                   +------+                   +------+
   .2|                                                      .4|
     |                                                        |
     |                                                        |
     |                  +------+    +------+                  |
     |  10.0.1.0/24     |      |    |      |    10.0.4.0/24   |
    ------------------- |  r1  |    |  r5  | -------------------
           net1      .1 |      |    |      |.5     net4     
                        +------+    +------+                
                              
  \........ area 0.0.0.0 ......../\........ area 2.2.2.2 ......../
  
```
