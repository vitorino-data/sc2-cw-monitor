# SC2 CW Monitor

Página web que mostra, para os times do torneio de Clan Wars (StarCraft II, servidor US, 1v1), quem pode ser escalado em cada vaga de cada divisão: MMR máximo dos últimos 90 dias, MMR atual, jogos em 30/90 dias, temporada e carreira, e winrate contra cada raça. Também mostra a escalação mais forte provável de cada time.

Os dados vêm da API pública do [SC2 Pulse](https://sc2pulse.nephest.com/sc2) (uso não comercial, com crédito ao site).

## Como funciona

```
Navegador ──> Caddy (HTTPS) ──┬─ /sc2-monitor/        página (docs/)
                              ├─ /sc2-monitor/data/   latest.json gerado pelo coletor
                              ├─ /sc2-monitor/api/    botão "Atualizar dados" (servidor/api.py)
                              └─ /                    blog (futuro)

Botão "Atualizar dados" ──> servidor/api.py ──> coletor/coletar.py ──> /var/lib/sc2-monitor/data/latest.json
                                                                   └─> /var/lib/sc2-monitor/historico/AAAA-MM-DD.csv

git push no main ──> GitHub Actions (testes) ──> SSH na VPS ──> git pull + reinicia o serviço
```

| Pasta / arquivo | O que é |
|---|---|
| `config.json` | Times, clãs (pelo ID do SC2 Pulse), seu time, divisões, vagas e limites de MMR, mínimo de jogos |
| `coletor/` | Consulta o SC2 Pulse e gera os dados |
| `servidor/api.py` | API do botão "Atualizar dados" (pede um código, roda o coletor e informa o andamento) |
| `docs/` | A página web |
| `deploy/` | Script de preparação da VPS, configuração do Caddy e do serviço |
| `.github/workflows/ci-deploy.yml` | Testes em todo push e pull request; deploy na VPS a cada push no `main` |

## Regras de elegibilidade (regulamento)

- O MMR máximo dos últimos 90 dias (SC2 Pulse) não pode passar o limite da vaga.
- Pelo menos 20 jogos nos últimos 30 dias.
- Divisão 1: 4200 → 4500 → 4800 → 5100. Divisão 2: 3500 → 3800 → 4100 → 4400.
- As vagas de 3500 e 3800 da Divisão 2 proíbem off-race. Isso aparece como observação, mas não é verificado automaticamente.

Tudo isso fica no `config.json`.

## Colocar no ar na VPS (uma vez só)

### 1. Contratar a VPS

Na Hostinger, plano **KVM 1**:
- Sistema operacional: **Ubuntu 24.04** puro (sem painel de controle).
- Localização: **São Paulo / Brasil**.
- Defina a senha de root (ou cadastre sua chave SSH).

Anote o **IP** da VPS, que aparece no painel da Hostinger.

### 2. Domínio (pode ser feito depois)

No Registro.br, depois de registrar o domínio, vá em **DNS → Editar zona** e crie:
- Registro **A**, nome vazio (`@`), valor: IP da VPS
- Registro **A**, nome `www`, valor: IP da VPS

A propagação leva de alguns minutos a algumas horas. Sem domínio, o monitor funciona em `http://IP-DA-VPS/sc2-monitor/`, só que sem HTTPS.

### 3. Criar a chave de deploy (no seu computador)

No PowerShell (Windows) ou no terminal:

```
ssh-keygen -t ed25519 -f sc2-deploy -N "" -C github-actions
```

Isso cria dois arquivos: `sc2-deploy` (privada, vai para o GitHub) e `sc2-deploy.pub` (pública, vai para a VPS).

### 4. Preparar a VPS

```
ssh root@IP-DA-VPS
curl -fsSL https://raw.githubusercontent.com/vitorino-data/sc2-cw-monitor/main/deploy/preparar-vps.sh -o preparar-vps.sh
bash preparar-vps.sh pedreirodedados.com.br "COLE AQUI O CONTEÚDO DE sc2-deploy.pub"
```

Sem domínio ainda, troque o domínio por `""`. O script instala tudo, configura o firewall, roda a primeira coleta (de 5 a 10 minutos) e, no fim, mostra o **código de atualização** que você vai passar para os capitães.

Para mudar o código depois, edite `/etc/sc2-monitor.env` e rode `systemctl restart sc2-monitor-api`. Para colocar o domínio depois, rode o script de novo com o domínio. O endereço com `www` redireciona sozinho para o endereço sem `www`.

### 5. Ligar o deploy automático

No GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
- `VPS_HOST`: IP da VPS (ou o domínio)
- `VPS_SSH_KEY`: conteúdo inteiro do arquivo `sc2-deploy` (a chave privada)

A partir daí, cada push no `main` roda os testes e atualiza a VPS sozinho. Dá para acompanhar na aba **Actions**.

## Usar no dia a dia

- **Atualizar os dados:** na página, clique em **Atualizar dados**, digite o código e clique em **Atualizar agora**. A página recarrega sozinha quando terminar (uns 5 minutos, ou 10 com matchups).
- **Mudar times, clãs ou limites:** edite o `config.json` no GitHub e salve no `main`. O deploy roda sozinho, e depois é só clicar em Atualizar dados.
- **Compartilhar:** cada divisão tem seu link (`/sc2-monitor/#divisao-1`, `#divisao-2`), e o botão "Copiar link desta divisão" copia o link certo.
- **Achar o ID de um clã:** abra o clã no SC2 Pulse. O número em `clanId=` no endereço é o ID.

## Rodar no seu computador

```
python -m venv .venv
.venv\Scripts\activate        (Windows)   ou   source .venv/bin/activate
pip install -r requirements.txt
python coletor/coletar.py
python -m http.server -d docs 8000
```

e abra http://localhost:8000. O botão "Atualizar dados" só aparece no servidor.

Testes: `python -m unittest discover -s tests -v`

## Como contribuir

Nada vai direto no `main`: crie um branch, abra um pull request e faça o merge só com o CI verde. O `main` é publicado na VPS automaticamente.

## Limitações

- O winrate por matchup usa só as partidas que o SC2 Pulse registrou, que é parcial. Use como tendência.
- A API do SC2 Pulse permite cerca de 4 requisições por segundo. Uma coleta dos 5 times (~830 jogadores) leva uns 4 minutos, e uns 10 recalculando matchups.
- A regra de off-race não é verificada automaticamente.
