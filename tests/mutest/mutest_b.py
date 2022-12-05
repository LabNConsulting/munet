step("r1", "ls -l /home")
wait_step("r1", "ls -l /home", "xhopps", "fail", "Look for xhopps", timeout=1, interval=.25)
wait_step("r1", "ls -l /home", "chopps", "pass", "Look for chopps", timeout=1, interval=.25)
wait_step("r1", "ls -l /", "root", "pass", "Look for root", timeout=1, interval=.25)

step("host1", "ls -l /")
wait_step("host1", "ls -l /home", "xhopps", "fail", "Look for xhopps", timeout=1, interval=.25)
wait_step("host1", "ls -l /home", "chopps", "pass", "Look for chopps", timeout=1, interval=.25)
wait_step("host1", "ls -l /", "root", "pass", "Look for root", timeout=1, interval=.25)
