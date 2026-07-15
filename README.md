# Impacto Care

SaaS multi-tenant de gestão para profissionais de atendimento domiciliar. O MVP reúne pacientes, responsáveis, agenda, registros de atendimento, aceite simples do responsável, portal da família, financeiro, relatórios dinâmicos, billing preparado e painel administrativo.

## Decisões de arquitetura

- **Monólito modular:** um FastAPI e um React reduzem custo operacional e complexidade. Os domínios permanecem separados para extração futura, se necessária.
- **PostgreSQL compartilhado com `organization_id`:** opção de menor custo para o estágio bootstrapado. Todas as consultas de negócio aplicam o escopo da organização.
- **Aplicação stateless:** JWT no cliente e nenhuma sessão em memória. Permite adicionar réplicas atrás de um proxy sem alterar o código.
- **Infraestrutura portátil:** Docker Compose, PostgreSQL e Nginx funcionam em qualquer VPS Linux. Não há dependência de serviços proprietários.
- **Billing isolado:** `Plan` e `Subscription` guardam plano, ciclo, status e IDs externos. A integração futura entra por um adaptador ASAAS ou Mercado Pago, sem contaminar os módulos de negócio.
- **Relatórios dinâmicos:** os dados são agregados no momento da solicitação; não há custo de armazenamento de arquivos no MVP.

## Executar localmente

1. Copie `.env.example` para `.env` e troque `JWT_SECRET` e a senha do banco.
2. Execute `docker compose up --build`.
3. Acesse `http://localhost:5173`; documentação da API em `http://localhost:8000/docs`.

Para criar o primeiro administrador:

```bash
docker compose exec -e ADMIN_EMAIL=admin@exemplo.com -e ADMIN_PASSWORD='uma-senha-forte' api python -m app.seed
```

## Implantação econômica em VPS

Uma VPS Linux com 2 vCPU e 4 GB atende o início. Instale Docker e o plugin Compose, aponte o DNS e coloque Caddy ou Nginx no host para TLS automático. Mantenha apenas as portas 80/443 públicas; banco e API permanecem na rede Docker. Provedores nacionais ou com cobrança em reais podem ser comparados no momento da contratação.

Operação mínima recomendada:

- backup diário com `pg_dump`, criptografado e copiado para um segundo local;
- teste mensal de restauração;
- atualização mensal das imagens e dependências;
- logs do Docker com rotação e monitor de disponibilidade simples;
- segredos somente no `.env` do servidor, com permissão restrita.

## LGPD e segurança

O cadastro exige consentimento; há perfis profissional, familiar e administrador, isolamento por organização e trilha de auditoria nas mutações principais. O portal familiar filtra pacientes vinculados. Em produção, complemente com política de retenção, exportação/exclusão mediante solicitação, registro do fundamento legal, revisão de acessos e contrato com operadores. O aceite simples registra nome e instante, não substitui uma assinatura qualificada quando ela for juridicamente exigida.

## Estrutura

```text
backend/app/       configuração, segurança, modelos, API e seed
backend/alembic/   migrações PostgreSQL
backend/tests/     testes de API e isolamento funcional
frontend/src/      landing, autenticação e módulos do painel
```

## Roadmap (não implementado)

1. Adaptador de cobrança e webhooks idempotentes para ASAAS/Mercado Pago.
2. Assinaturas automáticas, régua de cobrança e emissão de comprovantes.
3. Catálogo público de profissionais, após validação do modelo e controles de privacidade.
4. Publicidade, somente após escala e consentimento adequado.

O catálogo, publicidade e cobrança automática não fazem parte deste MVP.


## Sentinela na mesma VPS

O guia completo de portas, domínios, Caddy, backups e atualização conjunta está em [`deploy/DEPLOY_DUAL.md`](deploy/DEPLOY_DUAL.md).
