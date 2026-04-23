# ARM / QEMU Platform Architecture Lab Series

A 13-chapter hands-on lab series covering the full Arm platform stack on QEMU — from exception levels through interrupt controllers, power management, ACPI, PCIe, and Neoverse SVE extensions.

Each chapter is a Jupyter notebook that launches a QEMU aarch64 VM, interacts with it via QMP (QEMU Machine Protocol) and serial console, and validates behavior through assertions. All labs run on macOS Apple Silicon (HVF acceleration) or Linux (KVM).

**Author:** Aruna Kumar — Senior SoC Firmware Architect, ex-Intel Sr. Director

## Chapters

### Verified end-to-end (shipping)

| # | Topic | What You Learn | Boot time (HVF) |
|---|-------|----------------|----|
| 01 | ARM Architecture Overview | ISA fundamentals, register model, instruction encoding | ~13 s |
| 02 | Memory Model | Physical memory map, hot-plug DIMM via QMP | ~13 s |
| 03 | Exception Levels | EL0-EL2 boot path, PSCI, dmesg inspection | ~13 s |
| 04 | GIC Interrupt Controller | GICv3 with ITS, MSI routing for virtio-pci | ~13 s |

Each chapter has its own integration test under `arm_qemu_labs/test_boot_integration_ch0N.py` that actually boots the VM and asserts on the lab's key observations.

### Work in progress (notebook stubs only, not yet verified)

| # | Topic | Status |
|---|-------|--------|
| 05 | PSCI — Power State Coordination Interface, CPU on/off/suspend | stub |
| 06 | SCMI — System Control & Management Interface, clock/power domains | stub |
| 07 | ACPI on ARM — MADT, GTDT, IORT tables | stub |
| 08 | Device Tree — DT parsing, boot-time hardware description | stub |
| 09 | SMMUv3 — IOMMU, DMA isolation | stub |
| 10 | VirtIO — Device emulation, hot-plug | stub |
| 11 | PCIe on ARM — MSI-X, BAR configuration, ECAM | stub |
| 12 | Linux Boot Path — Kernel sequence, initramfs | stub |
| 13 | Neoverse Specifics — SVE/SVE2, performance counters | stub |

Chapters 5–13 are API-migrated (current launcher signature, current firmware layout, `sudo dmesg` pattern) but have **not** been booted end-to-end on Apple Silicon. Each needs the same Tier-3 integration test as 1–4 before it ships to the public repo. Do not treat these as working labs — treat them as outlines that happen to compile.

## Shared Infrastructure

```
arm_qemu_labs/shared/
  qmp_client.py       QMP JSON socket client — query CPUs, memory, PCI; add/remove devices
  serial_console.py   Serial console over pexpect — pattern matching, timeout-safe reads
  qemu_launcher.py    QEMU lifecycle — free port allocation, accelerator detection (HVF/KVM)
  assert_lib.py       Test assertions — assert_true, assert_equal, assert_contains, assert_qmp_ok
```

## Running tests

```bash
source ~/arm_qemu_labs/.venv/bin/activate
python arm_qemu_labs/test_shared_modules.py            # 41 unit tests, ~5 s
python arm_qemu_labs/test_boot_integration.py          # Ch. 1 end-to-end, ~13 s
python arm_qemu_labs/test_boot_integration_ch02.py     # Ch. 2 memory hotplug
python arm_qemu_labs/test_boot_integration_ch03.py     # Ch. 3 EL markers + PSCI
python arm_qemu_labs/test_boot_integration_ch04.py     # Ch. 4 GIC + MSI + virtio
```

Each end-to-end test skips (not fails) if `~/arm_qemu_labs/{firmware,images}` is empty. See [`docs/TESTING.md`](docs/TESTING.md) for the full test architecture, tier coverage, and guidance on adding tests for new chapters.

## Setup

### Quick Start (macOS Apple Silicon)

```bash
# One-time: install QEMU, download image, build venv, register Jupyter kernel
bash arm_qemu_labs/setup_qemu_labs.sh

# Every session: activate the venv
source ~/arm_qemu_labs/.venv/bin/activate

# Verify shared modules (41 tests)
cd arm_qemu_labs && python test_shared_modules.py

# Open labs — pick the "ARM QEMU Labs (venv)" kernel inside Jupyter
jupyter lab ~/arm_qemu_labs/notebooks/
```

### Requirements

- **QEMU** >= 8.0 with `qemu-system-aarch64` (`brew install qemu`)
- **Python** 3.12 (the venv pins to `/opt/homebrew/bin/python3.12`)
- **macOS**: HVF acceleration (Apple Silicon) or **Linux**: KVM

The setup script (`setup_qemu_labs.sh`) handles Homebrew dependencies, downloads Ubuntu 24.04 ARM64 cloud image, creates a cloud-init seed ISO, builds an isolated Python venv at `~/arm_qemu_labs/.venv`, and registers a Jupyter kernel named **ARM QEMU Labs (venv)**.

## FAQ

**Q: Why a dedicated venv instead of `pip install` against the system Python?**
Homebrew can promote a new default `python3` whenever a dependency pulls it in (e.g. `brew install jupyterlab` pulled `python@3.14` on top of an existing `python@3.12`). Packages installed under the old default become invisible to the new one, and `#!/usr/bin/env python3` shebangs silently start resolving to the wrong interpreter. A project-scoped venv at `~/arm_qemu_labs/.venv` pins a single Python and isolates the labs from host-level churn.

**Q: Do I have to activate the venv every time?**
Yes, once per shell session: `source ~/arm_qemu_labs/.venv/bin/activate`. After activation, `python`, `pip`, `jupyter lab`, and `pytest` all resolve to the venv's binaries. Deactivate with `deactivate`.

**Q: Which kernel do I pick inside Jupyter?**
**ARM QEMU Labs (venv)**. The default `Python 3` kernel points at Homebrew's current default Python, which may not have `pexpect` installed — the notebook's first cell will fail with `ModuleNotFoundError`. Switch via *Kernel → Change Kernel…*.

**Q: I see `ModuleNotFoundError: No module named 'pexpect'` — what happened?**
Either the venv isn't activated, or the notebook is running against the wrong kernel. Diagnose:
```bash
which python            # should print ~/arm_qemu_labs/.venv/bin/python
python -c "import sys; print(sys.executable)"   # same
```
In Jupyter: *Kernel → Change Kernel → ARM QEMU Labs (venv)*.

**Q: A `brew upgrade` broke something — how do I recover?**
The venv survives brew upgrades as long as the base Python (3.12) is still installed. If `python@3.12` itself got removed, rebuild the venv:
```bash
rm -rf ~/arm_qemu_labs/.venv
bash arm_qemu_labs/setup_qemu_labs.sh
```
The script is idempotent — existing QEMU image, firmware, and seed ISO are reused.

**Q: How do I add a new Python dependency for a lab?**
Install it into the venv and update `requirements.txt`:
```bash
source ~/arm_qemu_labs/.venv/bin/activate
pip install <package>
pip freeze | grep <package> >> requirements.txt
```

**Q: First boot takes ~2 minutes — is that normal?**
Yes. First boot runs cloud-init, which installs `pciutils`, `xxd`, `device-tree-compiler`, and `acpica-tools` into the guest. Subsequent boots are ~15 s on HVF.

**Q: Why split-flash firmware (`edk2-aarch64-code.fd` + `varstore.fd`) instead of `-bios QEMU_EFI.fd`?**
Homebrew's QEMU formula stopped shipping `QEMU_EFI.fd` and moved to the split EDK2 layout: `edk2-aarch64-code.fd` (read-only code, 64 MB) plus `edk2-arm-vars.fd` (varstore template). On QEMU 9.x + HVF + Apple Silicon, the legacy `-bios` path silently produces zero serial output — UEFI never makes it out of its stub. The launcher uses `-drive if=pflash,unit=0,readonly=on` for code and `-drive if=pflash,unit=1` for a per-VM writable varstore copy. The setup script stages both files into `~/arm_qemu_labs/firmware/`.

If you have a stale `~/arm_qemu_labs/firmware/QEMU_EFI.fd` from an older setup run, the current `setup_qemu_labs.sh` deletes it automatically — it was almost certainly `efi-virtio.rom` (160 KB network boot ROM) misdetected by the old firmware-search fallback, not a real 64 MB UEFI image.

**Q: Why does the launcher add `-netdev user,id=net0` by default?**
The cloud-init `packages:` block in `seed.iso` installs `pciutils`, `device-tree-compiler`, `acpica-tools` via `apt-get` on first boot. Without networking, `apt-get update` hangs forever waiting for DNS that doesn't exist, and cloud-init never finishes — the guest boots but `ubuntu login:` appears late enough to blow the 180 s wait. User-mode virtio-net gives cloud-init a working `10.0.2.0/24` on the slirp stack with zero host config. Pass `network=False` to `QEMULauncher` for labs that need to study a network-less boot.

**Q: Why `-cpu cortex-a76` and what happens under HVF?**
Cortex-A76 is the closest QEMU-emulatable microarchitectural ancestor of Neoverse N1 (same ARMv8.2-A feature set, same pipeline family) — QEMU doesn't expose `neoverse-n1` as a `-cpu` model, so A76 is the stand-in for Neoverse fidelity under TCG.

Under **HVF on Apple Silicon**, this doesn't work: HVF is pass-through virtualization, so the `virt` machine only accepts `host`, `max`, `cortex-a53`, or `cortex-a57`. Passing `cortex-a76` raises `Invalid CPU model`. The launcher handles this transparently — when it detects HVF, it coerces the requested CPU to `host` and logs the swap:

```
[qemu_launcher] HVF cannot emulate -cpu 'cortex-a76' on the virt machine;
                coercing to 'host' (Apple Silicon pass-through)
```

Under TCG or KVM (Linux), the requested model is passed through unchanged. This means a single notebook works on both: Apple Silicon devs see their real M-series core via HVF; Linux/CI runs get a Neoverse-N1-adjacent TCG emulation. Consequence on HVF: `CPU implementer` in `/proc/cpuinfo` is `0x61` (Apple), not `0x41` (Arm Ltd) — an honest reflection of where the code is actually running.

**Q: I get `zsh: command not found: jupyter` — what went wrong?**
The venv isn't activated in this shell. If you removed Homebrew's global `jupyterlab` (recommended in the cleanup section below), there is no global `jupyter` to fall back on — you must activate the venv first:
```bash
source ~/arm_qemu_labs/.venv/bin/activate
```
To make this automatic, see the `armlab` alias below.

**Q: Is there a shortcut so I don't have to activate + `cd` every time?**
Yes. Add this alias to `~/.zshrc` once:
```bash
echo "alias armlab='source ~/arm_qemu_labs/.venv/bin/activate && cd ~/Claude_Projects/ARM_vs_x86/arm_qemu_labs'" >> ~/.zshrc
source ~/.zshrc
```
Then every new shell session is one command: `armlab`. Your prompt gains a `(.venv)` prefix and you land in the lab directory ready to run `jupyter lab notebooks/`.

### Optional cleanup after migrating to the venv

If you previously ran the old version of `setup_qemu_labs.sh` (pre-venv) and installed packages against system Python, these leftovers are harmless but can be removed:

```bash
# Brew's jupyterlab — superseded by the venv's copy.
# Safe to remove; the venv is self-contained under ~/arm_qemu_labs/.venv.
brew uninstall jupyterlab

# Stray pexpect in Homebrew's python@3.12 site-packages.
/opt/homebrew/bin/python3.12 -m pip uninstall --break-system-packages -y pexpect
```

Do **not** uninstall `python@3.12` itself — the venv's interpreter is a copy that references the Homebrew Cellar.

## Related

- [ARM Software Stack Series](https://github.com/cakesandcode/ARM_SW_Stack) — Arm HPC/AI software stack tutorials (compilers, math libraries, ML frameworks)
- [Silicon Photonics CPO](https://github.com/cakesandcode/CPO_Silicon_Photonics) — CPO platform architecture + Arm Neoverse firmware integration
- [armfirmware.substack.com](https://armfirmware.substack.com) — Published articles

## License

MIT
