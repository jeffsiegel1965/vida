#!/usr/bin/env bash
# One-shot setup for Vida node server (GMKtec M5 Plus).
# Run after Ubuntu Server 24.04 LTS is installed and SSH is accessible.
#
# Usage:
#   scp setup_node_server.sh jeff-siegel@<ip>:
#   ssh jeff-siegel@<ip> ./setup_node_server.sh

set -euo pipefail

HOSTNAME="node-server"
USER="jeff-siegel"
KASPA_DIR="/home/$USER/kaspa-node"
TAO_DIR="/home/$USER/tao-node"
LOGS_DIR="/home/$USER/logs"

echo "=== Vida Node Server Setup ==="
echo "Target: $HOSTNAME"
echo "Date: $(date)"
echo ""

# ── 1. System updates ──
echo ">>> Updating system..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  curl wget git ufw htop nvtop \
  build-essential pkg-config \
  libssl-dev libclang-dev \
  unzip jq screen

# ── 2. Firewall ──
echo ">>> Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 16110/tcp comment 'Kaspa P2P'
sudo ufw allow 16111/tcp comment 'Kaspa RPC'
sudo ufw allow 30333/tcp comment 'Bittensor P2P'
sudo ufw allow 9944/tcp comment 'Bittensor WebSocket'
sudo ufw allow 9933/tcp comment 'Bittensor RPC'
sudo ufw --force enable

# ── 3. Tuning ──
echo ">>> System tuning..."
# Increase max open files for nodes
grep -q "nofile" /etc/security/limits.conf || {
  echo "$USER soft nofile 65535" | sudo tee -a /etc/security/limits.conf
  echo "$USER hard nofile 65535" | sudo tee -a /etc/security/limits.conf
}
# Disable swap (not needed, better perf without)
sudo swapoff -a 2>/dev/null || true

# ── 4. Kaspa Node ──
echo ">>> Installing Kaspa node..."
mkdir -p "$KASPA_DIR" "$LOGS_DIR"

# Download latest kaspad binary
KASPA_VERSION="v2.0.1"
wget -q -O /tmp/kaspad.tar.gz \
  "https://github.com/kaspanet/kaspad/releases/download/$KASPA_VERSION/kaspad-linux-amd64.tar.gz" \
  || wget -q -O /tmp/kaspad.tar.gz \
  "https://github.com/kaspanet/rusty-kaspa/releases/download/$KASPA_VERSION/rusty-kaspa-linux-x86_64.tar.gz"

if [ -f /tmp/kaspad.tar.gz ]; then
  tar -xzf /tmp/kaspad.tar.gz -C "$KASPA_DIR" --strip-components=1 2>/dev/null || true
  rm /tmp/kaspad.tar.gz
  echo "Kaspa binary downloaded to $KASPA_DIR"
else
  echo "WARNING: Could not download Kaspa binary. Install manually from:"
  echo "  https://github.com/kaspanet/rusty-kaspa/releases"
fi

# Write Kaspa systemd service
sudo tee /etc/systemd/system/kaspad.service > /dev/null <<'SERVICE'
[Unit]
Description=Kaspa Node
After=network.target

[Service]
Type=simple
User=jeff-siegel
WorkingDirectory=/home/jeff-siegel/kaspa-node
ExecStart=/home/jeff-siegel/kaspa-node/kaspad --utxoindex
Restart=always
RestartSec=30
StandardOutput=append:/home/jeff-siegel/logs/kaspad.log
StandardError=append:/home/jeff-siegel/logs/kaspad.err

[Install]
WantedBy=multi-user.target
SERVICE

# ── 5. Bittensor Subtensor Node ──
echo ">>> Installing Bittensor subtensor node..."
mkdir -p "$TAO_DIR"

# Install Rust (required for subtensor)
if ! command -v rustc &>/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source "$HOME/.cargo/env"
fi

# Clone and build subtensor
if [ ! -d "$TAO_DIR/subtensor" ]; then
  git clone https://github.com/opentensor/subtensor.git "$TAO_DIR/subtensor"
  cd "$TAO_DIR/subtensor"
  git checkout main
  echo "Building subtensor (this takes 10-30 minutes)..."
  cargo build --release --features=runtime-params --manifest-path node/Cargo.toml
  echo "Subtensor built."
else
  echo "Subtensor already cloned, updating..."
  cd "$TAO_DIR/subtensor"
  git pull
  cargo build --release --features=runtime-params --manifest-path node/Cargo.toml
fi

# Write subtensor systemd service
sudo tee /etc/systemd/system/subtensor.service > /dev/null <<'SERVICE'
[Unit]
Description=Bittensor Subtensor Node
After=network.target

[Service]
Type=simple
User=jeff-siegel
WorkingDirectory=/home/jeff-siegel/tao-node/subtensor
ExecStart=/home/jeff-siegel/tao-node/subtensor/target/release/node-template --chain /home/jeff-siegel/tao-node/subtensor/specs/finney.json --pruning archive --name "VidaNode"
Restart=always
RestartSec=30
StandardOutput=append:/home/jeff-siegel/logs/subtensor.log
StandardError=append:/home/jeff-siegel/logs/subtensor.err
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
SERVICE

# ── 6. Enable services ──
echo ">>> Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable kaspad
sudo systemctl enable subtensor
sudo systemctl start kaspad
echo "Kaspa node started (subtensor will start after reboot or manual start)"

# ── 7. Monitoring ──
echo ">>> Setting up monitoring..."
# Write a simple status script
cat > /home/jeff-siegel/check_nodes.sh <<'SCRIPT'
#!/usr/bin/env bash
echo "=== Node Status ==="
echo ""
echo "--- Kaspa ---"
systemctl is-active --quiet kaspad && echo "  Status: RUNNING" || echo "  Status: STOPPED"
curl -s http://localhost:16110/health 2>/dev/null | jq . 2>/dev/null || echo "  (health endpoint not responding)"
echo ""
echo "--- Bittensor ---"
systemctl is-active --quiet subtensor && echo "  Status: RUNNING" || echo "  Status: STOPPED"
echo ""
echo "--- System ---"
echo "  CPU: $(nproc --all) cores"
echo "  RAM: $(free -h | awk '/Mem:/ {print $3 "/" $2}')"
echo "  Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2}')"
echo "  Uptime: $(uptime -p)"
SCRIPT
chmod +x /home/jeff-siegel/check_nodes.sh

# ── 8. SSH key setup ──
echo ">>> Setting up SSH directory..."
mkdir -p /home/jeff-siegel/.ssh
chmod 700 /home/jeff-siegel/.ssh

# ── Summary ──
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Services:"
echo "  kaspad     — sudo systemctl status kaspad"
echo "  subtensor  — sudo systemctl status subtensor"
echo ""
echo "Logs:"
echo "  $LOGS_DIR/kaspad.log"
echo "  $LOGS_DIR/subtensor.err"
echo "  $LOGS_DIR/subtensor.log"
echo "  $LOGS_DIR/subtensor.err"
echo ""
echo "Check status:"
echo "  ./check_nodes.sh"
echo ""
echo "Next steps:"
echo "  1. ssh-copy-id to this machine from your main desktop"
echo "  2. Let me know the IP — I'll configure Vida to use this node"
echo "  3. Monitor sync: tail -f $LOGS_DIR/kaspad.log"
echo "  4. Subtensor sync: tail -f $LOGS_DIR/subtensor.log"
echo "     (subtensor will take several hours to sync the first time)"
echo ""
echo "Done: $(date)"