match_step("r1", "ls -l /home", "xhopps", "pass", "Look for xhopps")
match_step("r1", "ls -l /home", "chopps", "pass", "Look for chopps")
match_step("r1", "ls -l /", "root", "pass", "Look for root")

match_step("host1", "ls -l /home", "xhopps", "pass", "Look for xhopps")
match_step("host1", "ls -l /home", "chopps", "pass", "Look for chopps")
match_step("host1", "ls -l /", "root", "pass", "Look for root")
