# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# December 3 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
import pytest


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    "Pause or invoke CLI as directed by config"
    outcome = yield

    if call.when != "call":
        return

    report = outcome.get_result()
    if not call.excinfo:
        rstr = "PASSED"
    elif call.excinfo.typename == "Skipped":
        rstr = "SKIPPED"
    else:
        # modname = item.parent.module.__name__
        rstr = "FAILED"

    uprops = item.user_properties
    if not uprops:
        return

    sumrep = "\n".join(x[1] for x in uprops if isinstance(x[0], int))
    # item.add_report_section("call", "steps", sumrep)
    report.sections.append(("lunit summary", sumrep))
    #report.longrepr = None


@pytest.hookimpl(hookwrapper=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    tw = terminalreporter

    tw.write_sep("=", " PASSES ", green = True, bold=True)

    def reports(reports, **kwargs):
        for rep in reports:
            if not rep.sections:
                continue
            msg = tw._getfailureheadline(rep)
            tw.write_sep("_", msg, **kwargs)
            tw._outrep_summary(rep)

    #for k, v in tw.stats.items():
    reports(tw.stats.get("passed"), green=True, bold=True)
    # reports(tw.stats.get("failed"), red=True, bold=True)

    yield
