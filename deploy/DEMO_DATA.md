# Conta de demonstração para mídia

Os dados são fictícios e ficam isolados na organização `Impacto Care — Demonstração Fisioterapia`.

## Criar

Na VPS, dentro de `/opt/impacto-care`:

```bash
read -s -p "Senha da conta demo: " DEMO_PASSWORD && echo
docker compose -f docker-compose.yml -f docker-compose.kinghost.yml exec -T \
  -e DEMO_USER_PASSWORD="$DEMO_PASSWORD" api python -m app.demo_seed
unset DEMO_PASSWORD
```

Login padrão: `demo.fisioterapia@impactocg.com`.

Para usar outro e-mail, acrescente `-e DEMO_USER_EMAIL=novo@email.com` antes de `api`.

## Rollback integral

```bash
docker compose -f docker-compose.yml -f docker-compose.kinghost.yml exec -T \
  api python -m app.demo_seed --rollback
```

O rollback localiza a organização pelo marcador exclusivo e remove somente seus usuários, pacientes, responsáveis, agenda, registros, financeiro, disponibilidade, análises de IA, confirmações e assinatura.
