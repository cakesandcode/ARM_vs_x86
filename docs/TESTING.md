# Test architecture

Four tiers, increasing cost, decreasing frequency.

| Tier | File | Cost | What it proves | Gate |
|---|---|---|---|---|
| 1 — Unit + mocks | `arm_qemu_labs/test_shared_modules.py` | ~5 s | Python logic: ports, JSON parsing, CPU coercion, pflash/netdev arg building, firmware path validation | None (always runs) |
| 2 — Component integration | *(planned)* | ~30 s | Real `qemu-system-aarch64` spawn, QMP handshake, serial relay — isolated from the lab image | `qemu-system-aarch64` in PATH |
| 3 — End-to-end boot | `arm_qemu_labs/test_boot_integration_chNN.py` | ~13 s each | Full VM boot, cloud-init, chapter-specific QMP + serial assertions, clean teardown | `~/arm_qemu_labs/{firmware,images}` staged |
| 4 — Notebook execution | *(planned)* | ~3 min/chapter | Full notebook run via `nbclient`; assertion cells gate regressions | Chapter-specific |

## Running the tests

```bash
source ~/arm_qemu_labs/.venv/bin/activate

# Tier 1 — 41 unit tests, mocks only, no QEMU spawn
python arm_qemu_labs/test_shared_modules.py

# Tier 3 — per-chapter end-to-end, ~13 s each on Apple Silicon HVF
python arm_qemu_labs/test_boot_integration.py        # Ch. 1 login prompt
python arm_qemu_labs/test_boot_integration_ch02.py   # Ch. 2 memory hotplug
python arm_qemu_labs/test_boot_integration_ch03.py   # Ch. 3 PSCI + EL markers
python arm_qemu_labs/test_boot_integration_ch04.py   # Ch. 4 GIC + MSI + virtio

# Raw shell smoke test (bypasses the launcher)
bash arm_qemu_labs/test_boot_pflash.sh               # interactive, Ctrl+A X to exit
```

Each Tier 3 test `sys.exit(0)` with a `SKIP` message if `~/arm_qemu_labs/{firmware,images}` is empty — safe to run in environments where setup hasn't happened.

## Tier 1 coverage today

41 tests across four modules plus one cross-module check:

- `assert_lib`: 15 tests — assertion methods, summary/reset lifecycle, exception containment
- `qemu_launcher`: 10 tests — port allocation, accelerator detection, HVF CPU coercion, pflash+netdev command building, lifecycle, path validation (`firmware_code` size floor, missing file rejection), `memory_slots` / `maxmem` validation
- `qmp_client`: 7 tests — connect, JSON I/O, error handling, fragmented data
- `serial_console`: 6 tests — instantiation, connect, grep output
- `cross-module`: 1 test — port collision detection

## Tier 3 coverage today

Four chapters (Ch. 1–4). Each test boots the VM via `QEMULauncher`, waits for the login prompt, runs chapter-specific assertions via QMP and serial, and tears down cleanly in roughly 13 seconds on Apple Silicon HVF.

The tests are not just smoke tests — each asserts on a load-bearing behaviour the chapter teaches:

- **Ch. 1** — guest kernel reaches `ubuntu login:` prompt over serial; QMP `query-version` returns a structured response; `query-cpus-fast` returns at least one vCPU with a valid `cpu-index` field
- **Ch. 2** — `object-add memory-backend-ram` + `device_add pc-dimm` succeed; QMP `info memory-devices` reports `hotplugged: true` with the expected size
- **Ch. 3** — `sudo dmesg` contains a Linux/aarch64 banner; PSCI driver probe references are present; no synchronous-abort / unhandled-fault / EL3-exception lines appear
- **Ch. 4** — `/proc/interrupts` contains GIC-0 controller entries, MSI-routed interrupts, and virtio-device IRQ registrations (proves GICv3 ITS is routing)

These tests reproduce the notebooks' load-bearing QMP + serial assertions programmatically. They do not execute the notebooks themselves — full notebook execution under `nbclient` is the planned Tier 4.

## Why this split exists

The April 2026 firmware-detection incident (documented in the Ch. 1 Substack post) is the reference case. The repo shipped with 37 unit tests of the shared Python modules that all passed against mocks. Zero of them spawned a real `qemu-system-aarch64`. The notebook failed at every step when actually run on Apple Silicon — cortex-a76 rejected on HVF, a 160 KB `efi-virtio.rom` copied in as "firmware", missing `-netdev` causing cloud-init to hang, `json` imported two cells too late, stale QEMU processes holding disk locks.

Every one of those bugs would have been caught by a single Tier 3 test that boots the VM to a login prompt. The Tier 1 tests are still valuable — they run in five seconds and catch logic regressions before they hit the slower tiers — but they are not sufficient on their own. The rule going forward: every chapter ships with a Tier 3 test that boots the real VM and asserts on the chapter's load-bearing behaviour, gated on the user having actually run the setup script.

## Adding a test for a new chapter

Copy `arm_qemu_labs/test_boot_integration_ch02.py` as a template. Replace the chapter-specific assertions block (roughly lines 50-80) with the new chapter's observations. Keep the `require()` skip logic, the `QEMULauncher` construction, the `sc.wait_for_boot` and `sc.login` sequence, and the cleanup-in-`finally` pattern. Each test should run in under 30 seconds on Apple Silicon HVF; if it takes longer than that, the test is doing too much.
