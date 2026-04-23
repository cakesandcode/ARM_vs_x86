#!/usr/bin/env python3
"""
test_boot_integration_ch02.py — Ch. 2 integration test.

Boots with memory hotplug enabled (slots=2, maxmem=4G), hot-adds a 512 MiB
DIMM via QMP (memory-backend-ram + pc-dimm), and confirms QMP reports the
new range with hotplugged=true.

Skips if firmware/image not staged.

Run:
    python arm_qemu_labs/test_boot_integration_ch02.py
"""

import pathlib
import sys
import time

LABS_ROOT = pathlib.Path.home() / "arm_qemu_labs"
SHARED_DIR = LABS_ROOT / "shared"
FIRMWARE_CODE = LABS_ROOT / "firmware" / "edk2-aarch64-code.fd"
FIRMWARE_VARS = LABS_ROOT / "firmware" / "varstore.fd"
DISK_IMAGE = LABS_ROOT / "images" / "ubuntu-24.04-arm64.qcow2"
SEED_ISO = LABS_ROOT / "images" / "seed.iso"


def require(path: pathlib.Path) -> None:
    if not path.exists():
        print(f"SKIP: {path} not present. Run setup_qemu_labs.sh first.")
        sys.exit(0)


def main() -> int:
    for p in (FIRMWARE_CODE, FIRMWARE_VARS, DISK_IMAGE, SEED_ISO, SHARED_DIR):
        require(p)

    sys.path.insert(0, str(SHARED_DIR))
    from qemu_launcher import QEMULauncher
    from qmp_client import QMPClient
    from serial_console import SerialConsole

    launcher = QEMULauncher(
        cpu="cortex-a76", ram="2G", smp=1,
        maxmem="4G", memory_slots=2,
        firmware_code=str(FIRMWARE_CODE),
        firmware_vars=str(FIRMWARE_VARS),
        disk_image=str(DISK_IMAGE),
        seed_iso=str(SEED_ISO),
    )
    qmp = sc = None
    t0 = time.monotonic()
    try:
        launcher.launch()
        launcher.wait_ready(timeout=15)
        qmp = QMPClient(port=launcher.qmp_port); qmp.connect(timeout=30)
        sc = SerialConsole(port=launcher.serial_port); sc.connect(timeout=30)
        sc.wait_for_boot(timeout=240)

        # Hot-add a 512 MiB DIMM via QMP.
        r1 = qmp.send_command("object-add", {
            "qom-type": "memory-backend-ram", "id": "mem1",
            "size": 512 * 1024 * 1024,
        })
        assert r1.get("return") == {}, f"object-add failed: {r1}"

        r2 = qmp.send_command("device_add", {
            "driver": "pc-dimm", "id": "dimm1", "memdev": "mem1",
        })
        assert r2.get("return") == {}, f"device_add failed: {r2}"

        time.sleep(1)
        # Use structured QMP (not HMP) so the test doesn't break if the
        # human-readable formatter changes.
        devs = qmp.send_command("query-memory-devices")
        dimms = [d for d in devs.get("return", [])
                 if d.get("type") == "dimm"]
        assert dimms, f"no DIMM returned by query-memory-devices: {devs!r}"
        dimm = dimms[0]["data"]
        assert dimm.get("hotplugged") is True, f"dimm not hotplugged: {dimm!r}"
        assert dimm.get("size") == 512 * 1024 * 1024, \
            f"unexpected dimm size: {dimm!r}"

        print(f"[test] PASS — memory hotplug ({time.monotonic()-t0:.1f}s)")
        return 0
    except Exception as exc:
        print(f"[test] FAIL — {type(exc).__name__}: {exc}")
        print(f"[test] QEMU log: {launcher.log_file}")
        return 1
    finally:
        for cleanup in (
            lambda: qmp.close() if qmp else None,
            lambda: sc.close() if sc else None,
            launcher.terminate,
        ):
            try: cleanup()
            except Exception: pass


if __name__ == "__main__":
    sys.exit(main())
