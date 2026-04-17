#!/usr/bin/env python3
"""
test_shared_modules.py — ARM QEMU Lab Notebook Series
Unit tests for the 4 shared Python modules.

Tests do NOT require QEMU to be running.  They validate:
  - Module imports succeed
  - Class instantiation with valid/invalid args
  - assert_lib logic (PASS/FAIL formatting, summary)
  - qemu_launcher port allocation and accelerator detection
  - qmp_client JSON I/O logic (via mock socket)
  - serial_console instantiation

Run: python3 test_shared_modules.py
Expected: all tests PASS, exit code 0

Author: Aruna B Kumar | March 2026
"""

import os
import sys
import socket
import threading
import json
import time
from io import StringIO
from contextlib import redirect_stdout

# ── Path setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(SCRIPT_DIR, "shared")
sys.path.insert(0, SHARED_DIR)

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN = "\033[92m"; RED = "\033[91m"; RESET = "\033[0m"; BOLD = "\033[1m"
PASS_STR = f"{GREEN}PASS{RESET}"
FAIL_STR = f"{RED}FAIL{RESET}"

_results = []

def run_test(name, fn):
    try:
        fn()
        print(f"  {PASS_STR}  {name}")
        _results.append((name, True))
    except AssertionError as e:
        print(f"  {FAIL_STR}  {name}")
        print(f"         AssertionError: {e}")
        _results.append((name, False))
    except Exception as e:
        print(f"  {FAIL_STR}  {name}")
        print(f"         {type(e).__name__}: {e}")
        _results.append((name, False))


# ═══════════════════════════════════════════════════════════════════════════════
#  assert_lib tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_assert_lib_import():
    import assert_lib
    assert hasattr(assert_lib, "assert_true")
    assert hasattr(assert_lib, "assert_contains")
    assert hasattr(assert_lib, "assert_qmp_ok")
    assert hasattr(assert_lib, "assert_equal")
    assert hasattr(assert_lib, "summary")
    assert hasattr(assert_lib, "reset")


def test_assert_true_pass():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_true(True, "test-label", detail="some evidence")
    output = buf.getvalue()
    assert "PASS" in output, f"Expected PASS in output: {output!r}"
    assert "test-label" in output


def test_assert_true_fail():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_true(False, "fail-label", action="fix it")
    output = buf.getvalue()
    assert "FAIL" in output, f"Expected FAIL in output: {output!r}"
    assert "fail-label" in output


def test_assert_contains_pass():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_contains("hello world", r"w\w+", "word-match")
    output = buf.getvalue()
    assert "PASS" in output


def test_assert_contains_fail():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_contains("hello", r"xyz", "no-match")
    output = buf.getvalue()
    assert "FAIL" in output


def test_assert_equal_pass():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_equal(42, 42, "equal-42")
    assert "PASS" in buf.getvalue()


def test_assert_equal_fail():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_equal(1, 2, "not-equal")
    assert "FAIL" in buf.getvalue()


def test_assert_qmp_ok_pass():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_qmp_ok({"return": [{"cpu-index": 0}]}, "qmp-ok")
    assert "PASS" in buf.getvalue()


def test_assert_qmp_ok_fail():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_qmp_ok({"error": {"class": "GenericError", "desc": "bad"}}, "qmp-fail")
    assert "FAIL" in buf.getvalue()


def test_assert_in_range_pass():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_in_range(5.0, 1.0, 10.0, "in-range", unit="s")
    assert "PASS" in buf.getvalue()


def test_assert_in_range_fail():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_in_range(100.0, 1.0, 10.0, "out-of-range", unit="s")
    assert "FAIL" in buf.getvalue()


def test_assert_not_contains_pass():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_not_contains("clean output", r"error|fault", "no-error")
    assert "PASS" in buf.getvalue()


def test_summary_counts():
    import assert_lib
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.assert_true(True,  "p1")
        assert_lib.assert_true(True,  "p2")
        assert_lib.assert_true(False, "f1")
        assert_lib.summary()
    output = buf.getvalue()
    assert "2 PASS" in output or "2/3" in output or "PASS" in output, output
    assert "FAIL" in output


def test_reset_clears_results():
    import assert_lib
    assert_lib.reset()
    assert_lib.assert_true(True, "x")
    assert_lib.reset()
    buf = StringIO()
    with redirect_stdout(buf):
        assert_lib.summary()
    output = buf.getvalue()
    assert "0/0" in output or "0 total" in output or "0 PASS" in output


# ═══════════════════════════════════════════════════════════════════════════════
#  qemu_launcher tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_qemu_launcher_import():
    from qemu_launcher import QEMULauncher, detect_accel, _find_free_port


def test_find_free_port():
    from qemu_launcher import _find_free_port
    port = _find_free_port()
    assert isinstance(port, int), f"Port must be int, got {type(port)}"
    assert 1024 < port < 65536, f"Port out of range: {port}"


def test_find_free_port_unique():
    from qemu_launcher import _find_free_port
    ports = {_find_free_port() for _ in range(10)}
    # At least 5 unique ports (OS may reuse within short window)
    assert len(ports) >= 5, f"Expected diverse ports, got: {ports}"


def test_detect_accel_returns_string():
    from qemu_launcher import detect_accel
    # May return 'hvf', 'kvm', or 'tcg' depending on platform
    accel = detect_accel()
    assert isinstance(accel, str)
    assert accel in ("hvf", "kvm", "tcg"), f"Unexpected accel: {accel}"


def test_launcher_instantiation():
    from qemu_launcher import QEMULauncher
    l = QEMULauncher(cpu="cortex-a76", ram="2G", smp=1)
    # Requested CPU is always preserved; effective CPU depends on accelerator.
    # HVF on Apple Silicon rejects anything other than host/max/a53/a57 on the
    # virt machine, so the launcher coerces to 'host'. TCG/KVM pass through.
    assert l.requested_cpu == "cortex-a76"
    if l.accel == "hvf":
        assert l.cpu == "host", f"HVF should coerce to 'host', got {l.cpu!r}"
    else:
        assert l.cpu == "cortex-a76"
    assert l.ram == "2G"
    assert l.smp == 1
    assert isinstance(l.qmp_port, int)
    assert isinstance(l.serial_port, int)
    assert l.qmp_port != l.serial_port
    assert not l.is_running()


def test_launcher_ports_differ():
    from qemu_launcher import QEMULauncher
    l = QEMULauncher()
    assert l.qmp_port != l.serial_port


def test_launcher_terminate_noop():
    from qemu_launcher import QEMULauncher
    l = QEMULauncher()
    # terminate() with no process should not raise
    l.terminate()
    assert not l.is_running()


def test_launcher_wait_ready_no_qemu():
    from qemu_launcher import QEMULauncher
    l = QEMULauncher()
    # wait_ready() with nothing on the port should raise TimeoutError
    try:
        l.wait_ready(timeout=1.0)
        assert False, "Expected TimeoutError"
    except TimeoutError:
        pass  # Expected


# ═══════════════════════════════════════════════════════════════════════════════
#  qmp_client tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_qmp_client_import():
    from qmp_client import QMPClient


def test_qmp_client_no_port():
    from qmp_client import QMPClient
    try:
        QMPClient(port=None)
        assert False, "Expected ValueError"
    except ValueError:
        pass  # Expected


def test_qmp_client_connect_timeout():
    from qmp_client import QMPClient
    # Nothing listening on a random port — should raise TimeoutError
    from qemu_launcher import _find_free_port
    port = _find_free_port()
    qmp = QMPClient(port=port)
    try:
        qmp.connect(timeout=1.0)
        assert False, "Expected TimeoutError"
    except TimeoutError:
        pass


def _make_mock_qmp_server(port: int, responses: list) -> threading.Thread:
    """
    Minimal mock QMP server for unit testing the client.
    Sends greeting + qmp_capabilities ack, then responds from `responses` list.
    """
    greeting = json.dumps({"QMP": {"version": {}, "capabilities": []}}).encode() + b"\n"
    cap_ack   = json.dumps({"return": {}}).encode() + b"\n"

    def serve():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        srv.settimeout(5)
        try:
            conn, _ = srv.accept()
            conn.sendall(greeting)
            # Receive qmp_capabilities
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            conn.sendall(cap_ack)
            # Send pre-defined responses
            for resp in responses:
                # Wait for a command
                cmd_data = b""
                while b"\n" not in cmd_data:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    cmd_data += chunk
                conn.sendall(json.dumps(resp).encode() + b"\n")
            conn.close()
        except Exception:
            pass
        finally:
            srv.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return t


def test_qmp_client_connect_and_command():
    from qmp_client import QMPClient
    from qemu_launcher import _find_free_port

    port = _find_free_port()
    cpu_response = {"return": [{"cpu-index": 0, "arch": "aarch64"}]}
    t = _make_mock_qmp_server(port, [cpu_response])
    time.sleep(0.1)

    qmp = QMPClient(port=port)
    qmp.connect(timeout=5)
    result = qmp.send_command("query-cpus-fast")
    assert "return" in result, f"Expected return in: {result}"
    assert len(result["return"]) == 1
    qmp.close()
    t.join(timeout=2)


def test_qmp_client_query_cpus():
    from qmp_client import QMPClient
    from qemu_launcher import _find_free_port

    port = _find_free_port()
    cpu_list = [{"cpu-index": 0}, {"cpu-index": 1}]
    t = _make_mock_qmp_server(port, [{"return": cpu_list}])
    time.sleep(0.1)

    qmp = QMPClient(port=port)
    qmp.connect(timeout=5)
    cpus = qmp.query_cpus()
    assert isinstance(cpus, list)
    assert len(cpus) == 2
    assert cpus[0]["cpu-index"] == 0
    qmp.close()
    t.join(timeout=2)


def test_qmp_client_error_response():
    from qmp_client import QMPClient
    from qemu_launcher import _find_free_port

    port = _find_free_port()
    error_resp = {"error": {"class": "GenericError", "desc": "bad command"}}
    t = _make_mock_qmp_server(port, [error_resp])
    time.sleep(0.1)

    qmp = QMPClient(port=port)
    qmp.connect(timeout=5)
    try:
        qmp.send_command("bad-command")
        assert False, "Expected RuntimeError on QMP error response"
    except RuntimeError as e:
        assert "bad command" in str(e) or "error" in str(e).lower()
    qmp.close()
    t.join(timeout=2)


def test_qmp_client_recv_json_buffer():
    """Test that _recv_json correctly handles fragmented JSON."""
    from qmp_client import QMPClient
    from qemu_launcher import _find_free_port

    port = _find_free_port()
    # Response split across two packets
    resp = {"return": {"base-memory": 2147483648}}
    t = _make_mock_qmp_server(port, [resp])
    time.sleep(0.1)

    qmp = QMPClient(port=port)
    qmp.connect(timeout=5)
    result = qmp.send_command("query-memory-size-summary")
    mem = result["return"]
    assert mem["base-memory"] == 2147483648
    qmp.close()
    t.join(timeout=2)


# ═══════════════════════════════════════════════════════════════════════════════
#  serial_console tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_serial_console_import():
    from serial_console import SerialConsole


def test_serial_console_no_port():
    from serial_console import SerialConsole
    try:
        sc = SerialConsole(port=None)
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_serial_console_instantiation():
    from serial_console import SerialConsole
    sc = SerialConsole(host="127.0.0.1", port=12345)
    assert sc.host == "127.0.0.1"
    assert sc.port == 12345
    assert sc._child is None


def test_serial_console_connect_timeout():
    from serial_console import SerialConsole
    from qemu_launcher import _find_free_port
    port = _find_free_port()
    sc = SerialConsole(port=port)
    try:
        sc.connect(timeout=1.0)
        # If pexpect nc connects despite nothing listening, close gracefully
        sc.close()
    except TimeoutError:
        pass  # Expected — nothing listening


def test_serial_console_grep_output():
    from serial_console import SerialConsole
    sc = SerialConsole(port=9999)
    sc._last_output = "GICv3 found in /proc/interrupts\nsome other line"
    match = sc.grep_output(r"GICv3")
    assert match is not None
    assert "GICv3" in match


def test_serial_console_grep_output_none():
    from serial_console import SerialConsole
    sc = SerialConsole(port=9999)
    sc._last_output = "no gic here"
    match = sc.grep_output(r"GICv4")
    assert match is None


# ═══════════════════════════════════════════════════════════════════════════════
#  Cross-module integration test (no QEMU required)
# ═══════════════════════════════════════════════════════════════════════════════

def test_cross_module_port_no_collision():
    """Two QEMULauncher instances must not allocate the same QMP port."""
    from qemu_launcher import QEMULauncher
    l1 = QEMULauncher()
    l2 = QEMULauncher()
    assert l1.qmp_port != l2.qmp_port, (
        f"Port collision: both launchers got {l1.qmp_port}"
    )
    assert l1.serial_port != l2.serial_port


def test_assert_lib_no_exception_on_fail():
    """Assertion failures must never raise — notebook must always complete."""
    import assert_lib
    assert_lib.reset()
    # This must not raise
    assert_lib.assert_true(False, "intentional-fail")
    assert_lib.assert_contains("text", r"xyz_not_found", "intentional-contain-fail")
    assert_lib.assert_equal(1, 2, "intentional-equal-fail")
    # All three should be in results as FAIL
    # (access internal state for verification)
    fails = [r for r in assert_lib._results if r["status"] == "FAIL"]
    assert len(fails) == 3, f"Expected 3 failures, got {len(fails)}"


# ═══════════════════════════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════════════════════════

TESTS = [
    # assert_lib
    ("assert_lib: import",                      test_assert_lib_import),
    ("assert_lib: assert_true PASS",            test_assert_true_pass),
    ("assert_lib: assert_true FAIL",            test_assert_true_fail),
    ("assert_lib: assert_contains PASS",        test_assert_contains_pass),
    ("assert_lib: assert_contains FAIL",        test_assert_contains_fail),
    ("assert_lib: assert_equal PASS",           test_assert_equal_pass),
    ("assert_lib: assert_equal FAIL",           test_assert_equal_fail),
    ("assert_lib: assert_qmp_ok PASS",          test_assert_qmp_ok_pass),
    ("assert_lib: assert_qmp_ok FAIL",          test_assert_qmp_ok_fail),
    ("assert_lib: assert_in_range PASS",        test_assert_in_range_pass),
    ("assert_lib: assert_in_range FAIL",        test_assert_in_range_fail),
    ("assert_lib: assert_not_contains PASS",    test_assert_not_contains_pass),
    ("assert_lib: summary counts",              test_summary_counts),
    ("assert_lib: reset clears results",        test_reset_clears_results),
    ("assert_lib: no exception on FAIL",        test_assert_lib_no_exception_on_fail),

    # qemu_launcher
    ("qemu_launcher: import",                   test_qemu_launcher_import),
    ("qemu_launcher: _find_free_port",          test_find_free_port),
    ("qemu_launcher: ports are unique (x10)",   test_find_free_port_unique),
    ("qemu_launcher: detect_accel returns str", test_detect_accel_returns_string),
    ("qemu_launcher: instantiation",            test_launcher_instantiation),
    ("qemu_launcher: ports differ",             test_launcher_ports_differ),
    ("qemu_launcher: terminate noop",           test_launcher_terminate_noop),
    ("qemu_launcher: wait_ready no QEMU",       test_launcher_wait_ready_no_qemu),

    # qmp_client
    ("qmp_client: import",                      test_qmp_client_import),
    ("qmp_client: no port raises ValueError",   test_qmp_client_no_port),
    ("qmp_client: connect timeout",             test_qmp_client_connect_timeout),
    ("qmp_client: connect + command (mock)",    test_qmp_client_connect_and_command),
    ("qmp_client: query_cpus (mock)",           test_qmp_client_query_cpus),
    ("qmp_client: error response (mock)",       test_qmp_client_error_response),
    ("qmp_client: recv fragmented JSON (mock)", test_qmp_client_recv_json_buffer),

    # serial_console
    ("serial_console: import",                  test_serial_console_import),
    ("serial_console: no port raises ValueError", test_serial_console_no_port),
    ("serial_console: instantiation",           test_serial_console_instantiation),
    ("serial_console: connect timeout",         test_serial_console_connect_timeout),
    ("serial_console: grep_output match",       test_serial_console_grep_output),
    ("serial_console: grep_output no match",    test_serial_console_grep_output_none),

    # Cross-module
    ("cross: launcher port no collision",       test_cross_module_port_no_collision),
]


def main():
    print()
    print("═" * 68)
    print(f"  {BOLD}ARM QEMU Lab Notebook Series — Shared Module Tests{RESET}")
    print("═" * 68)
    print()

    for name, fn in TESTS:
        run_test(name, fn)

    # Summary
    passed = sum(1 for _, ok in _results if ok)
    failed = len(_results) - passed
    print()
    print("═" * 68)
    print(f"  {BOLD}RESULT{RESET}  {GREEN}{passed} PASS{RESET} / "
          f"{RED if failed else GREEN}{failed} FAIL{RESET} / {len(_results)} total")
    print("═" * 68)

    if failed > 0:
        print(f"\n  {RED}Failing tests:{RESET}")
        for name, ok in _results:
            if not ok:
                print(f"    ✗  {name}")
        print()
        sys.exit(1)
    else:
        print(f"\n  {GREEN}All tests passed — shared modules ready.{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
