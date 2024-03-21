OSPF Double Virtual-Link Simulation
===================================

This simulation demonstrates configuring nested virtual-links in FRRouting
through Munet.

It is possible to configure nested virtual-links in FRRouting. In this
simulation, for example, area 2.2.2.2 is connected to the backbone over
area 1.1.1.1. This then allows area 3.3.3.3 to connect to the backbone by
establishing a virtual link over area 2.2.2.2
