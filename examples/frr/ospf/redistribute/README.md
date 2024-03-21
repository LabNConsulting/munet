Route Redistribution OSPF Simulation
====================================

This simulation demonstrates redistributiong routes in OSPF through an
FRRouting simulation in Munet.

Router r2 is connected to a route external to OSPF. Through using the
`redistribute` clicmd, however, these routes can be accepted into OSPF for
redistribution to other routers.

```

   +------+                   +------+                  
   |      |    10.0.1.0/24    |      |    192.168.2.0/24   
   |  r1  | ----------------- |  r2  | -------------------
   |      |.1     net1      .2|      |.2       net2      
   +------+                   +------+                  
   
 \....... area 0.0.0.0 ........../
  
```
