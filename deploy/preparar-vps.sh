#!/usr/bin/env bash
# Prepara uma VPS Ubuntu 24.04 limpa para rodar o SC2 CW Monitor.
# Rode UMA vez, como root:
#   curl -fsSL https://raw.githubusercontent.com/vitorino-data/sc2-cw-monitor/main/deploy/preparar-vps.sh -o preparar-vps.sh
#   bash preparar-vps.sh pedreirodedados.com.br "ssh-ed25519 AAAA... github-actions"
# Argumentos:
#   1) domínio (opcional; sem domínio o site fica em http://IP-DA-VPS/sc2-monitor/)
#   2) chave pública SSH que o GitHub Actions vai usar para o deploy (opcional, dá para adicionar depois)
set -euo pipefail

DOMINIO="${1:-}"
CHAVE_DEPLOY="${2:-}"
REPO="https://github.com/vitorino-data/sc2-cw-monitor.git"
APP=/opt/sc2-cw-monitor

echo "==> Atualizando o sistema e instalando pacotes"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3-venv caddy ufw unattended-upgrades

echo "==> Usuários: 'sc2' roda o serviço, 'deploy' recebe as atualizações do GitHub"
id sc2 >/dev/null 2>&1 || useradd --system --home /var/lib/sc2-monitor --shell /usr/sbin/nologin sc2
id deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/bash deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
if [ -n "$CHAVE_DEPLOY" ]; then
  grep -qxF "$CHAVE_DEPLOY" /home/deploy/.ssh/authorized_keys 2>/dev/null || echo "$CHAVE_DEPLOY" >> /home/deploy/.ssh/authorized_keys
  chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys
fi
# O usuário deploy só pode reiniciar o serviço do monitor, nada além disso.
echo "deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart sc2-monitor-api" > /etc/sudoers.d/sc2-deploy
chmod 440 /etc/sudoers.d/sc2-deploy

echo "==> Código em $APP"
if [ ! -d "$APP/.git" ]; then git clone "$REPO" "$APP"; fi
chown -R deploy:deploy "$APP"
sudo -u deploy python3 -m venv "$APP/.venv"
sudo -u deploy "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

echo "==> Pastas de dados"
install -d -o sc2 -g sc2 /var/lib/sc2-monitor /var/lib/sc2-monitor/data /var/lib/sc2-monitor/historico
install -d /var/www/blog
[ -f /var/www/blog/index.html ] || echo '<!doctype html><meta charset="utf-8"><title>Pedreiro de Dados</title><p>Em construção. <a href="/sc2-monitor/">SC2 CW Monitor</a></p>' > /var/www/blog/index.html

echo "==> Configuração do serviço"
if [ ! -f /etc/sc2-monitor.env ]; then
  CODIGO="$(tr -dc 'a-z0-9' </dev/urandom | head -c 10)"
  cat > /etc/sc2-monitor.env <<ENV
CODIGO_ATUALIZACAO=$CODIGO
SC2_DATA_DIR=/var/lib/sc2-monitor/data
SC2_HIST_DIR=/var/lib/sc2-monitor/historico
SC2_LOG_FILE=/var/lib/sc2-monitor/ultima-coleta.log
ENV
  chmod 640 /etc/sc2-monitor.env && chown root:sc2 /etc/sc2-monitor.env
fi
cp "$APP/deploy/sc2-monitor-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sc2-monitor-api

echo "==> Servidor web (Caddy, com HTTPS automático quando houver domínio)"
SITE="${DOMINIO:-:80}"
sed "s|__SITE__|$SITE|" "$APP/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

echo "==> Firewall: só SSH, HTTP e HTTPS"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Primeira coleta (leva uns 5 a 10 minutos)"
sudo -u sc2 env $(grep -v '^#' /etc/sc2-monitor.env | xargs) "$APP/.venv/bin/python" "$APP/coletor/coletar.py"

echo
echo "Pronto!"
if [ -n "$DOMINIO" ]; then echo "Monitor: https://$DOMINIO/sc2-monitor/"; else echo "Monitor: http://$(curl -fsS https://api.ipify.org 2>/dev/null || echo IP-DA-VPS)/sc2-monitor/"; fi
echo "Código de atualização: $(grep CODIGO_ATUALIZACAO /etc/sc2-monitor.env | cut -d= -f2)"
echo "(para trocar o código: edite /etc/sc2-monitor.env e rode 'systemctl restart sc2-monitor-api')"
