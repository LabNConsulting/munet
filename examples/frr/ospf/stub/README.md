OSPF NSSA Simulation
====================

This simulation demonstrates configuring both types of NSSA areas in
FRRouting through Munet.

Area 0.0.0.0 is the backbone area, and contains ABR's r1 and r2. It is
connected to three areas including:

* Area 1.1.1.1
    * Regular area
 
* Area 2.2.2.2
    * Stubby area

* Area 3.3.3.3
    * Totally Stubby Area

```
        /''''' area 0.0.0.0 ''''\  /'''''''' area 1.1.1.1 '''''''''\
 
   +------+                   +------+                   +------+
   |      |    10.0.1.0/24    |      |    10.0.2.0/24    |      |
   |  r1  | ----------------- |  r2  | ----------------- |  r3  |
   |      |.1     net1      .2|      |.2     net2      .3|      |
   +------+                   +------+                   +------+
   .1| .1|
     |   |
     |   |                    +------+
     |   |    10.0.3.0/24     |      |
     |  --------------------- |  r4  |
     |           net3      .4 |      |
     |                        +------+
     |                        
     |  \..... area 2.2.2.2 (Stub) ..../
     |
     |
     |                        +------+ 
     |        10.0.4.0/24     |      | 
    ------------------------- |  r5  | 
                 net4      .5 |      | 
                              +------+ 
                                   
  \....... area 3.3.3.3 (Stub) ......../
  
```
