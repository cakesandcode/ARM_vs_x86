"""
qemu_launcher.py — ARM QEMU Lab Notebook Series
Manages the QEMU process lifecycle for all 13 lab notebooks.

Responsibilities:
  - HVF detection on macOS Apple Silicon; kvm on Linux; tcg as fallback
  - Free TCP port allocation for QMP and serial sockets
  - Launch qemu-system-aarch64 as a non-blocking subprocess
  - Expose launch(), wait_ready(), terminate(), is_running()
  - Write QEMU stdout/stderr to a log file for post-lab inspection

Author: Aruna B Kumar | March 2026
Target: macOS Apple Silicon (HVF) — qemu-system-aarch64
"""

import os
import signal
import socket
import subprocess
import tempfile
import time


# ── Port allocation ────────────────────────────────────────────────────────────

def _find_free_port() -> int:
    """Return an OS-allocated free TCP port (bind-release trick)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


# ── Accelerator detection ──────────────────────────────────────────────────────

def detect_accel() -> str:
    """
    Detect the best available QEMU accelerator.
    Priority: hvf (macOS) → kvm (Linux) → tcg (software).
    """
    try:
        result = subprocess.run(
            ["qemu-system-aarch64", "-accel", "help"],
            capture_output=True, text=True, timeout=5
        )
        output = (result.stdout + result.stderr).lower()
        if "hvf" in output:
            return "hvf"
        if "kvm" in output:
            return "kvm"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "tcg"


# ── QEMULauncher ──────────────────────────────────────────────────────────────

class QEMULauncher:
    """
    Launch and manage a single qemu-system-aarch64 instance.

    Usage:
        launcher = QEMULauncher(firmware=..., disk_image=...)
        launcher.launch()
        launcher.wait_ready()
        # ... use QMPClient / SerialConsole ...
        launcher.terminate()
    """

    def __init__(
        self,
        machine: str = "virt",
        cpu: str = "cortex-a76",
        ram: str = "2G",
        smp: int = 1,
        firmware: str = None,
        disk_image: str = None,
        seed_iso: str = None,
        extra_args: list = None,
        log_file: str = None,
    ):
        """
        Parameters
        ----------
        machine     : QEMU -machine type (default: virt)
        cpu         : QEMU -cpu model (default: cortex-a76)
        ram         : RAM size string (default: 2G)
        smp         : vCPU count (default: 1)
        firmware    : Path to QEMU_EFI.fd or other BIOS/UEFI image
        disk_image  : Path to guest disk (qcow2)
        seed_iso    : Path to cloud-init seed ISO (meta-data + user-data)
        extra_args  : Additional raw QEMU CLI arguments
        log_file    : Path for QEMU stdout/stderr log; auto-generated if None
        """
        self.machine = machine
        self.ram = ram
        self.smp = smp
        self.firmware = firmware
        self.disk_image = disk_image
        self.seed_iso = seed_iso
        self.extra_args = extra_args or []
        if log_file:
            self.log_file = log_file
        else:
            fd, self.log_file = tempfile.mkstemp(suffix=".log", prefix="qemu_lab_")
            os.close(fd)  # Close fd; QEMU opens the file itself

        # Allocate ports before launch so callers can configure clients
        self.qmp_port = _find_free_port()
        self.serial_port = _find_free_port()
        self.accel = detect_accel()

        # HVF on Apple Silicon is pass-through virtualization: the `virt`
        # machine only accepts host/max/cortex-a53/cortex-a57. Anything else
        # (e.g. cortex-a76, neoverse-n1) causes QEMU to exit with
        # "Invalid CPU model". Coerce to 'host' and record the original
        # request so notebooks can keep a semantically meaningful default
        # while still booting on HVF without per-chapter edits.
        self.requested_cpu = cpu
        _HVF_VIRT_OK = {"host", "max", "cortex-a53", "cortex-a57"}
        if self.accel == "hvf" and cpu not in _HVF_VIRT_OK:
            print(f"[qemu_launcher] HVF cannot emulate -cpu {cpu!r} on the "
                  f"virt machine; coercing to 'host' (Apple Silicon pass-through)")
            self.cpu = "host"
        else:
            self.cpu = cpu

        self._proc = None
        self._log_fh = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def launch(self) -> "QEMULauncher":
        """
        Start the QEMU subprocess.  Non-blocking — returns immediately.
        Call wait_ready() to confirm QMP is accepting connections.
        """
        cmd = self._build_cmd()
        self._log_fh = open(self.log_file, "w")
        self._proc = subprocess.Popen(
            cmd,
            stdout=self._log_fh,
            stderr=self._log_fh,
            preexec_fn=os.setsid,   # own process group → clean SIGTERM
        )
        print(f"[qemu_launcher] PID {self._proc.pid}  accel={self.accel}")
        print(f"[qemu_launcher] QMP  tcp://127.0.0.1:{self.qmp_port}")
        print(f"[qemu_launcher] UART tcp://127.0.0.1:{self.serial_port}")
        print(f"[qemu_launcher] Log  {self.log_file}")
        return self

    def wait_ready(self, timeout: float = 10.0) -> bool:
        """
        Block until the QMP TCP port accepts a connection.
        Raises TimeoutError if QEMU does not start within `timeout` seconds.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc and self._proc.poll() is not None:
                raise RuntimeError(
                    f"QEMU exited unexpectedly (rc={self._proc.returncode}). "
                    f"Check log: {self.log_file}"
                )
            try:
                with socket.create_connection(
                    ("127.0.0.1", self.qmp_port), timeout=1
                ):
                    pass
                print(f"[qemu_launcher] QMP port ready (+{time.monotonic():.1f}s)")
                return True
            except (ConnectionRefusedError, OSError):
                time.sleep(0.25)
        raise TimeoutError(
            f"QMP port {self.qmp_port} not ready after {timeout}s. "
            f"Check log: {self.log_file}"
        )

    def terminate(self) -> None:
        """Send SIGTERM to the QEMU process group; SIGKILL after 5 s."""
        if self._proc is None:
            return
        if self._proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                self._proc.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None
        self._proc = None
        print("[qemu_launcher] QEMU terminated")

    def is_running(self) -> bool:
        """True if the QEMU subprocess is alive."""
        return self._proc is not None and self._proc.poll() is None

    # ── Internals ──────────────────────────────────────────────────────────────

    def _build_cmd(self) -> list:
        cmd = [
            "qemu-system-aarch64",
            "-machine", f"{self.machine},accel={self.accel}",
            "-cpu", self.cpu,
            "-m", self.ram,
            "-smp", str(self.smp),
            "-nographic",
            "-no-reboot",
            # Serial console → TCP (pexpect connects here)
            "-serial", f"tcp::{self.serial_port},server,nowait",
            # QMP control socket
            "-qmp", f"tcp::{self.qmp_port},server,nowait",
        ]
        if self.firmware:
            cmd += ["-bios", str(self.firmware)]
        if self.disk_image:
            cmd += [
                "-drive",
                f"file={self.disk_image},if=virtio,format=qcow2,cache=writethrough",
            ]
        if self.seed_iso:
            cmd += [
                "-drive",
                f"file={self.seed_iso},if=virtio,format=raw,media=cdrom,readonly=on",
            ]
        cmd += self.extra_args
        return cmd
