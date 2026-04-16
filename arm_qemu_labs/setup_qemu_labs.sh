#!/usr/bin/env bash
# setup_qemu_labs.sh — ARM QEMU Lab Notebook Series
# One-time environment setup for macOS Apple Silicon.
# Run: bash setup_qemu_labs.sh
#
# Author: Aruna B Kumar | March 2026
# Target: macOS Apple Silicon (HVF) + Python 3.12 arm64

set -euo pipefail

LABS_ROOT="${HOME}/arm_qemu_labs"
IMAGES_DIR="${LABS_ROOT}/images"
FIRMWARE_DIR="${LABS_ROOT}/firmware"
SHARED_DIR="${LABS_ROOT}/shared"
VENV_DIR="${LABS_ROOT}/.venv"
KERNEL_NAME="arm-qemu-labs"
KERNEL_DISPLAY="ARM QEMU Labs (venv)"

UBUNTU_IMAGE_URL="https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-arm64.img"
UBUNTU_IMG_NAME="ubuntu-24.04-arm64.qcow2"

CONSOLE_USER="ubuntu"
CONSOLE_PASS="arm-lab-2026"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Check macOS Apple Silicon ─────────────────────────────────────────────────
check_platform() {
    if [[ "$(uname)" != "Darwin" ]]; then
        warn "This script targets macOS Apple Silicon. HVF may not be available on $(uname)."
    fi
    arch_out=$(uname -m)
    if [[ "${arch_out}" == "arm64" ]]; then
        info "Platform: macOS Apple Silicon (${arch_out}) — HVF acceleration available"
    else
        warn "Platform: ${arch_out} — HVF not available; labs will use TCG (slow)"
    fi
}

# ── Homebrew dependencies ─────────────────────────────────────────────────────
install_brew_deps() {
    if ! command -v brew &>/dev/null; then
        error "Homebrew not found. Install from https://brew.sh before running this script."
    fi

    info "Installing / verifying Homebrew packages …"

    local pkgs=(qemu dtc acpica wget)
    for pkg in "${pkgs[@]}"; do
        if brew list "${pkg}" &>/dev/null; then
            info "  ✓ ${pkg} already installed"
        else
            info "  Installing ${pkg} …"
            brew install "${pkg}"
        fi
    done

    # QEMU UEFI firmware for aarch64
    if brew list qemu-efi-aarch64 &>/dev/null 2>&1 || \
       brew list qemu &>/dev/null 2>&1; then
        info "  ✓ QEMU installed"
    fi
}

# ── Python dependencies (isolated venv) ───────────────────────────────────────
# Why a venv instead of `pip install --break-system-packages`:
#   Homebrew can promote a new default `python3` (e.g. 3.14) at any brew upgrade,
#   which hides packages installed under the previous default (e.g. 3.12) and
#   breaks the notebook kernel. A project-scoped venv pins the interpreter and
#   insulates the labs from host-level Python churn.
install_python_deps() {
    info "Creating isolated Python venv at ${VENV_DIR} …"

    # Prefer an explicit 3.12 interpreter; fall back to whatever `python3` is.
    local py_bin=""
    for candidate in \
        "/opt/homebrew/bin/python3.12" \
        "/opt/homebrew/opt/python@3.12/bin/python3.12" \
        "$(command -v python3.12 2>/dev/null || true)" \
        "$(command -v python3 2>/dev/null || true)"; do
        if [[ -n "${candidate}" && -x "${candidate}" ]]; then
            py_bin="${candidate}"
            break
        fi
    done
    [[ -z "${py_bin}" ]] && error "No python3 interpreter found. Install python@3.12: brew install python@3.12"

    local py_ver
    py_ver=$("${py_bin}" --version 2>&1)
    info "  Base Python : ${py_bin} (${py_ver})"

    if [[ -d "${VENV_DIR}" ]]; then
        info "  ✓ venv already exists"
    else
        "${py_bin}" -m venv "${VENV_DIR}"
        info "  ✓ venv created"
    fi

    local venv_py="${VENV_DIR}/bin/python"
    info "Installing pinned packages into venv …"
    "${venv_py}" -m pip install --quiet --upgrade pip
    "${venv_py}" -m pip install --quiet \
        "pexpect>=4.9.0,<5.0" \
        "jupyterlab>=4.1.0,<5.0" \
        "ipykernel" \
        "pytest>=7.4.0,<9.0"

    info "Registering Jupyter kernel '${KERNEL_NAME}' …"
    "${venv_py}" -m ipykernel install --user \
        --name "${KERNEL_NAME}" \
        --display-name "${KERNEL_DISPLAY}" >/dev/null

    info "  ✓ pexpect, jupyterlab, ipykernel, pytest installed"
    info "  ✓ Kernel '${KERNEL_DISPLAY}' registered"
}

# ── Directory structure ───────────────────────────────────────────────────────
create_dirs() {
    info "Creating directory structure at ${LABS_ROOT} …"
    mkdir -p "${IMAGES_DIR}" "${FIRMWARE_DIR}" "${SHARED_DIR}"
    # Copy shared modules from the script's directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -d "${SCRIPT_DIR}/shared" ]]; then
        cp -n "${SCRIPT_DIR}/shared/"*.py "${SHARED_DIR}/" 2>/dev/null || true
        info "  ✓ Shared modules copied to ${SHARED_DIR}"
    fi
}

# ── QEMU UEFI firmware ────────────────────────────────────────────────────────
setup_firmware() {
    local fw_dest="${FIRMWARE_DIR}/QEMU_EFI.fd"

    if [[ -f "${fw_dest}" ]]; then
        info "  ✓ Firmware already at ${fw_dest}"
        return
    fi

    info "Locating QEMU_EFI.fd …"

    # Try Homebrew QEMU share directory
    local brew_fw
    brew_fw=$(find "$(brew --prefix)/share" -name "QEMU_EFI.fd" 2>/dev/null | head -1)

    if [[ -n "${brew_fw}" ]]; then
        cp "${brew_fw}" "${fw_dest}"
        info "  ✓ Copied from ${brew_fw}"
    else
        warn "QEMU_EFI.fd not found in Homebrew share. Trying edk2 package …"
        brew_fw=$(find "$(brew --prefix)" -name "efi-virtio.rom" -o \
                                          -name "QEMU_EFI.fd" 2>/dev/null | head -1)
        if [[ -n "${brew_fw}" ]]; then
            cp "${brew_fw}" "${fw_dest}"
            info "  ✓ Copied from ${brew_fw}"
        else
            warn "Could not locate QEMU_EFI.fd automatically."
            echo ""
            echo "  Manual steps:"
            echo "  1. Install qemu-efi-aarch64: brew install qemu"
            echo "     (the QEMU_EFI.fd is in $(brew --prefix)/share/qemu/)"
            echo "  2. Copy it: cp $(brew --prefix)/share/qemu/QEMU_EFI.fd ${fw_dest}"
            echo ""
        fi
    fi
}

# ── Ubuntu cloud image ────────────────────────────────────────────────────────
download_image() {
    local raw_img="${IMAGES_DIR}/ubuntu-24.04-arm64.img"
    local qcow2_img="${IMAGES_DIR}/${UBUNTU_IMG_NAME}"

    if [[ -f "${qcow2_img}" ]]; then
        info "  ✓ Disk image already at ${qcow2_img}"
        return
    fi

    info "Downloading Ubuntu 24.04 ARM64 cloud image …"
    info "  URL: ${UBUNTU_IMAGE_URL}"
    info "  Destination: ${raw_img}"
    wget -c --progress=bar:force -O "${raw_img}" "${UBUNTU_IMAGE_URL}"

    info "Converting to qcow2 format (adds snapshot capability) …"
    qemu-img convert -f qcow2 -O qcow2 "${raw_img}" "${qcow2_img}"
    # Resize to 10 GB to give labs enough space
    qemu-img resize "${qcow2_img}" 10G
    rm -f "${raw_img}"
    info "  ✓ ${qcow2_img} (10 GiB)"
}

# ── cloud-init seed ISO ───────────────────────────────────────────────────────
create_seed_iso() {
    local seed_dir="${IMAGES_DIR}/seed"
    local seed_iso="${IMAGES_DIR}/seed.iso"

    if [[ -f "${seed_iso}" ]]; then
        info "  ✓ Seed ISO already at ${seed_iso}"
        return
    fi

    info "Creating cloud-init seed ISO …"
    mkdir -p "${seed_dir}"

    # meta-data (instance identity)
    cat > "${seed_dir}/meta-data" <<EOF
instance-id: arm-qemu-lab-001
local-hostname: arm-lab
EOF

    # user-data (configure user, SSH, packages)
    cat > "${seed_dir}/user-data" <<EOF
#cloud-config
users:
  - name: ${CONSOLE_USER}
    plain_text_passwd: "${CONSOLE_PASS}"
    lock_passwd: false
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash

# Disable cloud-init password lockout
chpasswd:
  expire: false

# Disable SSH host key check for local lab use
ssh_pwauth: true

# Pre-install lab tools
packages:
  - pciutils
  - xxd
  - device-tree-compiler
  - acpica-tools
  - net-tools
  - iproute2

package_update: true
package_upgrade: false

# Set hostname
hostname: arm-lab

# Final message on first boot
final_message: |
  ARM QEMU Lab environment ready.
  User: ${CONSOLE_USER} / Password: ${CONSOLE_PASS}
EOF

    # Create ISO using hdiutil (macOS) or genisoimage (Linux)
    if command -v hdiutil &>/dev/null; then
        hdiutil makehybrid -o "${seed_iso}" "${seed_dir}" \
            -hfs-volume-name "cidata" -joliet -iso \
            -default-volume-name "cidata" \
            -quiet 2>/dev/null || \
        # Fallback: use mkisofs if available
        mkisofs -output "${seed_iso}" -volid "cidata" \
            -joliet -rock "${seed_dir}" 2>/dev/null || true
    elif command -v genisoimage &>/dev/null; then
        genisoimage -output "${seed_iso}" -volid "cidata" \
            -joliet -rock "${seed_dir}"
    elif command -v mkisofs &>/dev/null; then
        mkisofs -output "${seed_iso}" -volid "cidata" \
            -joliet -rock "${seed_dir}"
    else
        warn "No ISO creation tool found (hdiutil/genisoimage/mkisofs)."
        warn "Create ${seed_iso} manually with meta-data and user-data."
        warn "Files written to ${seed_dir}/"
        return
    fi

    info "  ✓ Seed ISO created at ${seed_iso}"
}

# ── Smoke test ────────────────────────────────────────────────────────────────
smoke_test() {
    info "Running smoke test …"

    # qemu-system-aarch64 present?
    if command -v qemu-system-aarch64 &>/dev/null; then
        ver=$(qemu-system-aarch64 --version | head -1)
        info "  ✓ ${ver}"
    else
        error "qemu-system-aarch64 not found after installation."
    fi

    # HVF check
    if qemu-system-aarch64 -accel help 2>&1 | grep -q "hvf"; then
        info "  ✓ HVF accelerator available"
    else
        warn "  HVF not listed — labs will run with TCG (significantly slower)"
    fi

    # Firmware
    if [[ -f "${FIRMWARE_DIR}/QEMU_EFI.fd" ]]; then
        info "  ✓ QEMU_EFI.fd present"
    else
        warn "  QEMU_EFI.fd not found — place it at ${FIRMWARE_DIR}/QEMU_EFI.fd"
    fi

    # Disk image
    if [[ -f "${IMAGES_DIR}/${UBUNTU_IMG_NAME}" ]]; then
        img_size=$(du -sh "${IMAGES_DIR}/${UBUNTU_IMG_NAME}" | cut -f1)
        info "  ✓ Disk image present (${img_size})"
    else
        warn "  Disk image not found at ${IMAGES_DIR}/${UBUNTU_IMG_NAME}"
    fi

    # venv + pexpect inside it
    if [[ -x "${VENV_DIR}/bin/python" ]] && \
       "${VENV_DIR}/bin/python" -c "import pexpect, jupyterlab" 2>/dev/null; then
        info "  ✓ venv healthy (pexpect + jupyterlab importable)"
    else
        warn "  venv missing or incomplete — re-run this script"
    fi

    info ""
    info "Setup complete."
    info ""
    info "Activate the venv for every lab session:"
    info "  source ${VENV_DIR}/bin/activate"
    info ""
    info "Then run:"
    info "  python test_shared_modules.py      # verify shared modules (37 tests)"
    info "  jupyter lab ${LABS_ROOT}/notebooks/"
    info ""
    info "In Jupyter, select the '${KERNEL_DISPLAY}' kernel."
    info ""
    info "Optional — one-shot shell alias (activate + cd):"
    info "  echo \"alias armlab='source ${VENV_DIR}/bin/activate && cd \$(pwd)'\" >> ~/.zshrc"
    info "  source ~/.zshrc"
    info "Then every new shell: type 'armlab'."
}

# ── Entry point ───────────────────────────────────────────────────────────────
main() {
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  ARM QEMU Lab Notebook Series — Environment Setup"
    echo "  Aruna B Kumar | March 2026"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    check_platform
    install_brew_deps
    install_python_deps
    create_dirs
    setup_firmware
    download_image
    create_seed_iso
    smoke_test
}

main "$@"
