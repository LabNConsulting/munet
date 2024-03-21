Multipoint OSPF Simulation
==========================

This simulation demonstrates multipoint networks in FRRouting through Munet.

Unless specified as non-broadcast or point-to-point through the
`ip ospf network` clicmd, each network will be a broadcast network and therefore
support many interfaces. This simulation demonstrates this proprery.

```
                                                         +------+
                                                         |      |
                                                         |  r3  |
                                                         |      |         
                                                         +------+         
   +------+                   +------+                     .3|        
   |      |    10.0.2.0/24    |      |    10.0.1.0/24        |
   |  r4  | ----------------- |  r1  | ------------------------    
   |      |.4     net2      .1|      |.1     net1            |
   +------+                   +------+                     .2|           
                                                         +------+         
                                                         |      |         
                                                         |  r2  |
                                                         |      | 
                                                         +------+

  \......................... area 0.0.0.0 ......................../
  
```
