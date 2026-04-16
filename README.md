# ARM / QEMU Platform Architecture Lab Series

A 13-chapter hands-on lab series covering the full Arm platform stack on QEMU — from exception levels through interrupt controllers, power management, ACPI, PCIe, and Neoverse SVE extensions.

Each chapter is a Jupyter notebook that launches a QEMU aarch64 VM, interacts with it via QMP (QEMU Machine Protocol) and serial console, and validates behavior through assertions. All labs run on macOS Apple Silicon (HVF acceleration) or Linux (KVM).

**Author:** Aruna Kumar — Senior SoC Firmware Architect, ex-Intel Sr. Director

## The 13 Chapters

| # | Topic | What You Learn |
|---|-------|----------------|
| 01 | ARM Architecture Overview | ISA fundamentals, register model, instruction encoding |
| 02 | Memory Model | Hierarchy, coherency, memory ordering |
| 03 | Exception Levels | EL0-EL3 privilege levels, secure vs non-secure world |
| 04 | GIC Interrupt Controller | Generic Interrupt Controller, IRQ routing, priorities |
| 05 | PSCI | Power State Coordination Interface, CPU on/off/suspend |
| 06 | SCMI | System Control & Management Interface, clock/power domains |
| 07 | ACPI on ARM | MADT, GTDT, IORT tables — how ARM platforms describe hardware |
| 08 | Device Tree | DT parsing, boot-time hardware description, FDT overlays |
| 09 | SMMUv3 | System Memory Management Unit, IOMMU, DMA isolation |
| 10 | VirtIO | Device emulation, hot-plug, virtio-net/blk/rng on ARM |
| 11 | PCIe on ARM | PCIe MSI-X interrupts, BAR configuration, ECAM |
| 12 | Linux Boot Path | Kernel boot sequence, initramfs, device probing |
| 13 | Neoverse Specifics | SVE/SVE2, Neoverse V3/N3 features, performance counters |

## Shared Infrastructure

```
arm_qemu_labs/shared/
  qmp_client.py       QMP JSON socket client — query CPUs, memory, PCI; add/remove devices
  serial_console.py   Serial console over pexpect — pattern matching, timeout-safe reads
  qemu_launcher.py    QEMU lifecycle — free port allocation, accelerator detection (HVF/KVM)
  assert_lib.py       Test assertions — assert_true, assert_equal, assert_contains, assert_qmp_ok
```

## Tests

```bash
cd arm_qemu_labs && python3 test_shared_modules.py
```

37 tests across 4 modules + 1 cross-module integration test:
- `assert_lib`: 14 tests (assertion methods, summary, reset)
- `qemu_launcher`: 8 tests (port allocation, accelerator detection, lifecycle)
- `qmp_client`: 7 tests (connect, JSON I/O, error handling, fragmented data)
- `serial_console`: 6 tests (instantiation, connect, grep output)
- `cross-module`: 1 test (port collision detection)

## Setup

### Quick Start (macOS Apple Silicon)

```bash
# One-time: install QEMU, download image, build venv, register Jupyter kernel
bash arm_qemu_labs/setup_qemu_labs.sh

# Every session: activate the venv
source ~/arm_qemu_labs/.venv/bin/activate

# Verify shared modules (37 tests)
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
