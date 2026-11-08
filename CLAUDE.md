# Regras do repositório

- **Nunca faça commit ou push direto no `main`.** Toda mudança vai num branch próprio e entra por pull request.
- O `main` é publicado automaticamente na VPS (workflow `ci-deploy.yml`), então só faça merge com o job `ci` verde.
- Antes de abrir o PR, rode `python -m unittest discover -s tests -v`.
- Textos para o usuário (página, README, mensagens) em português do Brasil.
