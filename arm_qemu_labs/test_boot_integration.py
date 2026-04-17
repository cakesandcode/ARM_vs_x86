#!/usr/bin/env python3
"""
test_boot_integration.py — Tier 3 end-to-end boot test for the Ch. 1 lab.

Exercises the real QEMULauncher + QMPClient + SerialConsole stack against
the staged firmware, qcow2 image, and seed ISO. Boots the VM, confirms
QMP responds, waits for the ubuntu login prompt over serial, tears down.

This is the single test that would have caught every bug discovered in the
April 2026 firmware-detection incident:
  - cortex-a76 rejected on HVF (coercion)
  - efi-virtio.rom mislabeled as QEMU_EFI.fd (160 KB instead of 64 MB)
  - missing -netdev causing cloud-init apt hang
  - disk write-lock on re-run without teardown

Skips (not fails) if firmware/image aren't staged, so it can live alongside
unit tests without breaking contributors who haven't run setup_qemu_labs.sh.

Run:
    source ~/arm_qemu_labs/.venv/bin/activate
    python arm_qemu_labs/test_boot_integration.py
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

BOOT_TIMEOUT = 240  # first-boot cloud-init adds ~30 s on top of kernel boot


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
        cpu="cortex-a76",
        ram="2G",
        smp=1,
        firmware_code=str(FIRMWARE_CODE),
        firmware_vars=str(FIRMWARE_VARS),
        disk_image=str(DISK_IMAGE),
        seed_iso=str(SEED_ISO),
    )
    qmp = None
    sc = None
    t0 = time.monotonic()
    try:
        launcher.launch()
        launcher.wait_ready(timeout=15)

        qmp = QMPClient(port=launcher.qmp_port)
        qmp.connect(timeout=30)

        ver = qmp.query_version()
        assert isinstance(ver.get("qemu", {}).get("major"), int), (
            f"QMP query-version shape unexpected: {ver}"
        )

        cpus = qmp.query_cpus()
        assert len(cpus) >= 1, f"query-cpus-fast returned empty: {cpus}"

        sc = SerialConsole(port=launcher.serial_port)
        sc.connect(timeout=30)

        print(f"[test] waiting up to {BOOT_TIMEOUT}s for login prompt...")
        sc.wait_for_boot(timeout=BOOT_TIMEOUT)

        elapsed = time.monotonic() - t0
        print(f"[test] PASS — guest reached login prompt in {elapsed:.1f}s")
        return 0

    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"[test] FAIL after {elapsed:.1f}s — {type(exc).__name__}: {exc}")
        if sc and sc._child:
            tail = (sc._child.before or "")[-2000:]
            print("[test] last 2000 chars of serial buffer:")
            print(tail)
        print(f"[test] QEMU log: {launcher.log_file}")
        return 1

    finally:
        # launcher.terminate() kills QEMU; sending QMP quit is redundant.
        # Use qmp.close() to release the socket cleanly.
        for cleanup in (
            lambda: qmp.close() if qmp else None,
            lambda: sc.close() if sc else None,
            launcher.terminate,
        ):
            try:
                cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
