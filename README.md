# Monitor de Clan Wars (SC2 Pulse)

Página web que mostra, para os clãs do torneio (servidor US, 1v1), quem pode ser escalado em cada divisão: MMR atual, MMR máximo em 90 dias, jogos na carreira/temporada/90d/30d e winrate contra cada raça.

Os dados vêm da API pública do [SC2 Pulse](https://sc2pulse.nephest.com/sc2) e são atualizados quando você clica no botão "Atualizar dados" da página. A página é estática (GitHub Pages), então não há servidor para manter e o custo é zero.

## Como funciona

```
GitHub Actions (quando você pede) ──> coletor/coletar.py ──> docs/data/latest.json  ──> página (GitHub Pages)
                                                  └─> dados/historico/AAAA-MM-DD.csv  (uma foto a cada atualização)
```

- `config.json`: lista de clãs, seu clã (fica destacado), divisões e limites de MMR.
- `coletor/`: código que consulta o SC2 Pulse.
- `docs/`: a página web.
- `worker/`: o serviço do botão "Atualizar dados" (Cloudflare Worker).
- `dados/historico/`: uma foto de cada jogador a cada atualização (só grava quem mudou), para consultar depois como estava numa data de corte.

## Atualizar os dados

Na página, clique em **Atualizar dados**, digite o código de atualização e clique em **Atualizar agora**. A página mostra o andamento e recarrega sozinha quando os dados novos chegam (uns 5 minutos, ou 10 se marcar "Recalcular winrate por matchup"). O código fica salvo no navegador de quem já digitou uma vez.

Por trás, o botão chama um pequeno serviço grátis no Cloudflare (`worker/worker.js`), que guarda a chave do GitHub em segredo e dispara a coleta no GitHub Actions. Assim ninguém precisa abrir o GitHub, e só quem sabe o código consegue atualizar.

### Configurar o botão (uma vez só)

1. **Token do GitHub:** em github.com → foto → Settings → Developer settings → Personal access tokens → *Fine-grained tokens* → **Generate new token**.
   - Repository access: *Only select repositories* → este repositório
   - Permissions → Repository permissions → **Actions: Read and write**
   - Gere e copie o token (começa com `github_pat_`)
2. **Cloudflare (grátis):** crie conta em dash.cloudflare.com → **Workers & Pages** → **Create** → **Create Worker** → nome `sc2-cw-atualizar` → **Deploy**.
3. Clique em **Edit code**, apague o conteúdo, cole o arquivo `worker/worker.js` e clique em **Deploy**.
4. No Worker, vá em **Settings → Variables and Secrets** e adicione:
   - `GITHUB_TOKEN` (tipo *Secret*): o token do passo 1
   - `CODIGO` (tipo *Secret*): o código que você vai passar para os capitães
   - `REPO` (tipo *Text*): `SEU-USUARIO/NOME-DO-REPO`
   - `ORIGEM` (tipo *Text*): o endereço da página, por exemplo `https://SEU-USUARIO.github.io` ou `https://cw.seudominio.com.br`
5. Copie o endereço do Worker (algo como `https://sc2-cw-atualizar.SEU-NOME.workers.dev`) e coloque em `"atualizador_url"` no `config.json`.

Também dá para atualizar pelo GitHub: aba **Actions** → "Atualizar dados do SC2 Pulse" → **Run workflow**.

## Colocar no ar (uma vez só)

1. Crie um repositório no GitHub e suba estes arquivos.
2. Em **Settings → Pages**, escolha *Deploy from a branch*, branch `main`, pasta `/docs`.
3. Em **Actions**, abra "Atualizar dados do SC2 Pulse" e clique em **Run workflow** para a primeira coleta.
4. A página fica em `https://SEU-USUARIO.github.io/NOME-DO-REPO/`.

### Domínio próprio (opcional)

Em **Settings → Pages → Custom domain**, digite o domínio (por exemplo `cw.seudominio.com.br`) e, no painel do seu registrador, crie um registro CNAME apontando para `SEU-USUARIO.github.io`. O HTTPS é ativado automaticamente.

## Mudar clãs ou limites

Edite o `config.json` direto no GitHub (ícone de lápis), salve e clique em Atualizar dados.

## Compartilhar com os capitães

Cada divisão tem seu link: `.../#divisao-1`, `.../#divisao-2` etc. O botão "Copiar link desta divisão" na página copia o link já com a divisão escolhida.

## Rodar no seu computador

```
pip install requests
python coletor/coletar.py
python -m http.server -d docs 8000
```

e abra http://localhost:8000.

## Limitações

- O SC2 Pulse não filtra por tag, então o coletor procura pelo texto e escolhe o clã US com a tag exata.
- O winrate por matchup usa só as partidas que o SC2 Pulse registrou, que é parcial. Use como tendência.
- A API permite cerca de 4 requisições por segundo. Uma coleta de 3 clãs (~140 jogadores) leva uns 20 segundos sem matchups e cerca de 1 minuto com matchups.
- Uso não comercial, com crédito ao SC2 Pulse.
