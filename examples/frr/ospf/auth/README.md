Authentication OSPF Simulation
==============================

This simulation demonstrates the OSPF authentication functionality through a
FRRouting simulation in Munet.

There are three different networks in this simulation:

* Network net1 has no authentication.
* Network net2 uses simple password authentication.
* Network net3 uses cryptographic authentication.

```
                             10.0.2.0/24        +------+
     ------------------------------------------ |      |
      |                         net2          .3|  r3  |         
      |.2                                       |      |         
   +------+                   +------+          +------+      
   |      |    10.0.1.0/24    |      |                   
   |  r2  | ----------------- |  r1  |                   
   |      |.2     net1      .1|      |                   
   +------+                   +------+          +------+         
      |.2                                       |      |         
      |                      10.0.4.0/24      .4|  r4  |         
     ------------------------------------------ |      |
                                net3            +------+


  \......................... area 0.0.0.0 ......................../
  
```
