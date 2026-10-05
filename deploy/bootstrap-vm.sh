#!/usr/bin/env bash
set -Eeuo pipefail

exec > >(tee -a /var/log/plotsrv-vm-bootstrap.log) 2>&1

USERNAME="samane"
USER_HOME="/home/${USERNAME}"

if [[ ${EUID} -ne 0 ]]; then
  echo "ERROR: this bootstrap must run as root." >&2
  exit 1
fi

echo "==> plotsrv VM bootstrap starting on $(hostname)"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  htop \
  jq \
  python3 \
  python3-pip \
  python3-venv \
  rsync \
  sudo \
  tmux \
  unzip

if ! id "${USERNAME}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash --groups sudo "${USERNAME}"
else
  usermod -aG sudo "${USERNAME}"
fi

# Key-only account. sudo remains passwordless because there is no local password.
passwd -l "${USERNAME}" >/dev/null 2>&1 || true

cat > "/etc/sudoers.d/${USERNAME}" <<EOF_SUDO
${USERNAME} ALL=(ALL) NOPASSWD:ALL
EOF_SUDO
chmod 0440 "/etc/sudoers.d/${USERNAME}"
visudo -cf "/etc/sudoers.d/${USERNAME}"

install -d -o "${USERNAME}" -g "${USERNAME}" -m 0700 "${USER_HOME}/.ssh"

if [[ ! -s /root/.ssh/authorized_keys ]]; then
  echo "ERROR: /root/.ssh/authorized_keys is missing or empty." >&2
  echo "Create the Droplet with your DigitalOcean SSH key selected." >&2
  exit 1
fi

install -o "${USERNAME}" -g "${USERNAME}" -m 0600 \
  /root/.ssh/authorized_keys "${USER_HOME}/.ssh/authorized_keys"

# Install uv for Sam's interactive/admin account.
install -d -o "${USERNAME}" -g "${USERNAME}" -m 0755 "${USER_HOME}/.local/bin"
runuser -u "${USERNAME}" -- env \
  HOME="${USER_HOME}" \
  UV_INSTALL_DIR="${USER_HOME}/.local/bin" \
  UV_NO_MODIFY_PATH=1 \
  sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

if ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "${USER_HOME}/.profile" 2>/dev/null; then
  printf '\n# Local user executables (uv, etc.)\nexport PATH="$HOME/.local/bin:$PATH"\n' \
    >> "${USER_HOME}/.profile"
fi
chown "${USERNAME}:${USERNAME}" "${USER_HOME}/.profile"

"${USER_HOME}/.local/bin/uv" --version
python3 --version

# SSH is key-only. Root key login remains available as a recovery path for now.
install -d -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/10-plotsrv-key-only.conf <<'EOF_SSH'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF_SSH

sshd -t
systemctl reload ssh

cat > /var/lib/plotsrv-vm-bootstrap-complete <<EOF_DONE
completed_at=$(date --iso-8601=seconds)
hostname=$(hostname)
admin_user=${USERNAME}
python=$(python3 --version 2>&1)
uv=$(${USER_HOME}/.local/bin/uv --version 2>&1)
EOF_DONE

echo "==> plotsrv VM bootstrap complete"
echo "==> Login: ssh ${USERNAME}@<droplet-ip>"
