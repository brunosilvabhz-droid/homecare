# Sentinela + Impacto Care na mesma VPS

Esta configuração preserva os domínios existentes do Sentinela e publica o Impacto Care sem conflito de portas.

## Mapa de serviços

| Sistema | Domínio | Porta local |
|---|---|---:|
| Sentinela web | `app.impactocg.com` | 5173 |
| Sentinela API | `api.impactocg.com` | 8000 |
| Impacto Care web | `care.impactocg.com` | 5180 |
| Impacto Care API | `api-care.impactocg.com` | 8010 |

Se o Sentinela usar portas internas diferentes, altere apenas os dois primeiros destinos no Caddyfile.

## 1. DNS

Crie registros `A` para `care` e `api-care`, apontando para o mesmo IP que já atende `app` e `api`.

## 2. Estrutura na VPS

```bash
sudo mkdir -p /opt/sentinela /opt/impacto-care /var/backups/impacto
sudo chown -R deploy:deploy /opt/sentinela /opt/impacto-care /var/backups/impacto
```

O Sentinela permanece em `/opt/sentinela`. Clone o Impacto Care:

```bash
git clone https://github.com/brunosilvabhz-droid/homecare.git /opt/impacto-care
cd /opt/impacto-care
cp deploy/impacto-care.env.example .env
nano .env
```

Gere os segredos:

```bash
openssl rand -hex 32
openssl rand -base64 36 | tr -dc 'A-Za-z0-9' | head -c 32
```

Use o primeiro valor em `JWT_SECRET` e o segundo como senha do PostgreSQL, repetindo a senha dentro de `DATABASE_URL`.

## 3. Iniciar os dois sistemas

```bash
cd /opt/sentinela
docker compose up -d --build

cd /opt/impacto-care
docker compose up -d --build
```

Confirme que não há conflito:

```bash
docker compose ps
curl http://127.0.0.1:8010/health
curl -I http://127.0.0.1:5180
```

## 4. Caddy e HTTPS

```bash
sudo cp /opt/impacto-care/deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Valide externamente:

```bash
curl -I https://app.impactocg.com
curl -I https://api.impactocg.com/health
curl -I https://care.impactocg.com
curl -I https://api-care.impactocg.com/health
```

## 5. Administrador do Impacto Care

```bash
cd /opt/impacto-care
docker compose exec -e ADMIN_EMAIL=admin@impactocg.com -e ADMIN_PASSWORD='TROQUE_ESTA_SENHA' api python -m app.seed
```

## 6. Backups separados

```bash
cd /opt/impacto-care
docker compose exec -T db pg_dump -U impactocare -d impactocare -Fc > /var/backups/impacto/impacto-care-$(date +%F-%H%M).dump
```

Mantenha também o procedimento de backup do banco do Sentinela. Copie os arquivos para um segundo local e teste restaurações.

## 7. Operação na VPS de 4 GB

Configure 2 GB de swap e acompanhe `docker stats`, `free -h`, `df -h` e `uptime`. Considere subir para 8 GB se a RAM permanecer acima de 75%, houver uso contínuo de swap ou carga de CPU próxima de 2.0.

## 8. Atualizações

```bash
cd /opt/sentinela
git pull
docker compose up -d --build

cd /opt/impacto-care
git pull
docker compose up -d --build
```

Faça backup antes de atualizações que incluam migrações de banco.
