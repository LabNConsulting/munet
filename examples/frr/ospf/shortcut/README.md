Shortcut OSPF Simulation
========================

This simulation demonstrates OSPF shortcut ABR's through a FRRouting simulation
in Munet.

Router r4 is configures as chortcut capable using the clicmd
`ospf abr-type shortcut`. This allows shorter routes between the two areas. For
example, it will take 2 hops for traffic from r3 to reach r5, as compared to
the 4 hops it would take traffic had to route through the backbone area.

```
       /''''''''''''''''''' area 0.0.0.0 '''''''''''''''''''\

   +------+                   +------+                   +------+
   |      |    10.0.1.0/24    |      |    10.0.6.0/24    |      |
   |  r2  | ----------------- |  r1  | ----------------- |  r6  |
   |      |.2     net1      .1|      |.1     net6      .6|      |
   +------+                   +------+                   +------+
     |.2                                                  .6|
     |                                                      |
     |                                                      |
     |                                                      |
     | 10.0.2.0/24                              10.0.5.0/24 |
     | net2                                            net5 |
     |                                                      |
     |                                                      |
     |                                                      |
     |.3                                                  .5|
   +------+                   +------+                   +------+
   |      |    10.0.3.0/24    |      |    10.0.4.0/24    |      |
   |  r3  | ----------------- |  r4  | ----------------- |  r5  |
   |      |.3     net3      .4|      |.4     net4      .5|      |
   +------+                   +------+                   +------+

 \........ area 1.1.1.1 ......../  \........ area 2.2.2.2 ......../
  
```
