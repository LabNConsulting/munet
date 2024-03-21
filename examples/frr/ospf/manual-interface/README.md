Manual Interface Simulation
===========================

This simulation demonstrates manually naming an interface through an OSPF
FRRouting simulation in Munet.

Munet will automatically populate interfaces with the names eth0, eth1,
eth2, ... so in order to changes the name of an interface, you can't only rename
it in the `.../frr.conf` files but you need to specify the name in
`./munet.yaml`
