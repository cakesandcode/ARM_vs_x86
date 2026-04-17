#!/usr/bin/env bash
# test_boot_pflash.sh — minimal boot test using pflash firmware pair.
#
# Diagnostic for root-cause verification: does the Ubuntu 24.04 ARM64
# cloud image reach a login prompt when booted with the modern
# edk2-aarch64-code.fd + varstore.fd flash pair instead of the legacy
# -bios QEMU_EFI.fd path (which was silently broken — the setup script
# had been copying efi-virtio.rom by mistake).
#
# Run: bash arm_qemu_labs/test_boot_pflash.sh
# Exit QEMU: Ctrl+A then X

set -euo pipefail

LABS_ROOT="${HOME}/arm_qemu_labs"
FIRMWARE_DIR="${LABS_ROOT}/firmware"
IMAGES_DIR="${LABS_ROOT}/images"

CODE_FD="${FIRMWARE_DIR}/edk2-aarch64-code.fd"
VARS_FD="${FIRMWARE_DIR}/varstore.fd"
DISK="${IMAGES_DIR}/ubuntu-24.04-arm64.qcow2"
SEED="${IMAGES_DIR}/seed.iso"

BREW_SHARE="$(brew --prefix)/share/qemu"

# ── Stage firmware files if missing ──────────────────────────────────────────
if [[ ! -f "${CODE_FD}" ]]; then
    echo "[stage] copying edk2-aarch64-code.fd …"
    cp "${BREW_SHARE}/edk2-aarch64-code.fd" "${CODE_FD}"
fi
if [[ ! -f "${VARS_FD}" ]]; then
    echo "[stage] copying edk2-arm-vars.fd → varstore.fd …"
    cp "${BREW_SHARE}/edk2-arm-vars.fd" "${VARS_FD}"
    chmod u+w "${VARS_FD}"
fi

echo "[stage] firmware directory:"
ls -la "${FIRMWARE_DIR}"

# ── Sanity-check disk + seed ISO ─────────────────────────────────────────────
[[ -f "${DISK}" ]] || { echo "FATAL: missing ${DISK}"; exit 1; }
[[ -f "${SEED}" ]] || { echo "FATAL: missing ${SEED}"; exit 1; }

# ── Kill any stale QEMU holding the qcow2 lock ───────────────────────────────
echo "[stage] clearing any stale qemu-system-aarch64 …"
pkill -f qemu-system-aarch64 2>/dev/null || true
sleep 1

# ── Launch ───────────────────────────────────────────────────────────────────
echo "[launch] starting QEMU — exit with Ctrl+A then X"
echo ""

qemu-system-aarch64 \
  -machine virt,accel=hvf \
  -cpu host -smp 1 -m 2G \
  -drive if=pflash,format=raw,unit=0,file="${CODE_FD}",readonly=on \
  -drive if=pflash,format=raw,unit=1,file="${VARS_FD}" \
  -drive if=virtio,file="${DISK}",format=qcow2,cache=writethrough \
  -drive if=virtio,file="${SEED}",format=raw,media=cdrom,readonly=on \
  -netdev user,id=net0 -device virtio-net-device,netdev=net0 \
  -nographic
