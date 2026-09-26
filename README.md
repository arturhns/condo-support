# CondoAgenda

Protótipo acadêmico do **PJI240** (Projeto Integrador em Computação II — Univesp).

Sistema web para consulta, reserva, reagendamento e cancelamento de áreas comuns de condomínio (salão, churrasqueira, quadra etc.), com calendário de disponibilidade, lista de convidados, e-mail de confirmação e painel da gestão.

> Etapa atual: o morador reserva, cancela e reagenda pela interface web; recebe e-mail (console ou API SendGrid); e pode usar a API REST autenticada em `/api/`.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose

## Subir o projeto

Copie o arquivo de ambiente (se ainda não existir) e suba os serviços:

```bash
cp .env.example .env
docker compose up --build
```

A aplicação fica em [http://localhost:8000](http://localhost:8000). O admin Django em [http://localhost:8000/admin/](http://localhost:8000/admin/).

Na primeira subida o `entrypoint.sh` aguarda o Postgres (quando não há `DATABASE_URL`), aplica `migrate` e `collectstatic`, e — se `DJANGO_SUPERUSER_PASSWORD` estiver definido — tenta `createsuperuser --noinput` (idempotente se o username já existir). Em seguida executa o `CMD` do Dockerfile (Gunicorn). O `docker-compose.yml` de desenvolvimento mantém o volume `.:/app` — alterações locais de código/templates entram no container sem rebuild.

## Login do morador

URL: [http://localhost:8000/contas/entrar/](http://localhost:8000/contas/entrar/)

O model `app.User` autenticado pelo Django usa **`USERNAME_FIELD = "username"`** (padrão do `AbstractUser`). Não alteramos o model nesta etapa.

No formulário de login você pode informar:

- o **username** gerado no seed (`morador1`, `morador2`, `staff`), ou
- o **e-mail** correspondente (`morador1@condo.local` etc.) — o formulário resolve para o username internamente.

Senha de todos os usuários do seed: `condo123`.

| Login (username) | E-mail | Papel |
|------------------|--------|--------|
| `staff` | `staff@condo.local` | gestão (staff; sem bloco) — use também `/admin/` |
| `morador1` | `morador1@condo.local` | morador — Torre Brisas / apto 36 |
| `morador2` | `morador2@condo.local` | morador — Torre Caminhos / apto 54 |

### Fluxo: criar reserva

Entrar como `morador1` → [Áreas comuns](http://localhost:8000/areas/) → abrir uma área → no calendário, escolher o dia → clicar num horário livre → preencher pessoas/convidados → Confirmar → a home [Minhas reservas](http://localhost:8000/) mostra o protocolo na message e na lista. Um e-mail de confirmação é disparado (ver seção E-mail abaixo).

### Fluxo: cancelar

Em Minhas reservas (ou no detalhe), use **Cancelar** se ainda estiver dentro do prazo (`Space.min_cancel_hours`, padrão 48h antes do início). A tela pede confirmação: “Tem certeza que deseja cancelar a reserva {protocol}?”. Fora do prazo, a reserva permanece confirmada e aparece message de erro (sem 500).

### Fluxo: reagendar

Em Minhas reservas (ou no detalhe), use **Reagendar** se o status for Confirmada e o início ainda for futuro. Abre o calendário da **mesma área** (`/reservas/<id>/reagendar/`). Ao clicar num horário livre, abre o **formulário** pré-preenchido (início/fim editáveis no mesmo dia, convidados e observações). Só o POST do formulário marca a original como **Reagendada** e cria uma nova **Confirmada** (`related_reservation` + convidados novos). Slot ocupado por outra reserva devolve erro no formulário.

## E-mail (requisito PJI240 — uso de API)

O requisito de **uso de API** deste projeto é o **consumo de uma API externa de e-mail** (SendGrid via Anymail). A API DRF em `/api/` é interface complementar do próprio app, não substitui esse requisito.

Backend escolhido pela env (sem `if` nas views):

| Situação | Comportamento |
|----------|----------------|
| `EMAIL_API_KEY` vazio | `django.core.mail.backends.console.EmailBackend` — o fluxo **não quebra**; o texto do e-mail aparece no **log do container** |
| `EMAIL_API_KEY` preenchido | Anymail + **SendGrid** (`anymail.backends.sendgrid.EmailBackend`) |

Alternativa documentada (não implementada por padrão): Resend — `EMAIL_BACKEND=anymail.backends.resend.EmailBackend` e a mesma `EMAIL_API_KEY` (chave Resend).

`DEFAULT_FROM_EMAIL` também vem do `.env`. Timeout curto na API; se o envio falhar, o erro é logado e a **reserva não é desfeita**.

### Ver o e-mail no log (sem chave)

Deixe `EMAIL_API_KEY=` vazio no `.env`, crie/cancele/reagende uma reserva e veja o stdout do web:

```bash
docker compose logs -f web
```

### Ligar a API SendGrid (com chave)

No `.env`:

```env
EMAIL_API_KEY=sua-chave-sendgrid
EMAIL_BACKEND=anymail.backends.sendgrid.EmailBackend
DEFAULT_FROM_EMAIL=CondoAgenda <nao-responda@seudominio.com>
```

Reinicie o web (`docker compose up -d --build web` se as dependências mudaram). Destinatário: sempre `reservation.user.email` (sem dados de outros moradores).

## API REST (DRF)

Todas as rotas exigem autenticação (`IsAuthenticated`). Com sessão Django (cookie após login no site) ou Basic Auth.

Exemplo — listar espaços autenticado (após login no browser, ou com Basic):

```bash
# Session: abra http://localhost:8000/api/spaces/ logado no mesmo browser
# Ou Basic Auth:
curl -u morador1:condo123 http://localhost:8000/api/spaces/
```

| Método | Caminho | Descrição |
|--------|---------|-----------|
| GET | `/api/spaces/` | Espaços ativos |
| GET | `/api/spaces/<slug>/availability/?date=YYYY-MM-DD` | Slots `{date, slots:[{start,end,available}]}` (sem nome de quem ocupou) |
| GET | `/api/reservations/me/` | Reservas do usuário autenticado |
| POST | `/api/reservations/` | Criar (`space`, `date`, `start_time`, `end_time`, `guest_names[]`, `notes`) |
| POST | `/api/reservations/<id>/cancel/` | Cancelar (só o dono) |
| POST | `/api/reservations/<id>/reschedule/` | Reagendar (`date`, `start_time`, `end_time`, `guest_names[]`) |

Morador só age nas próprias reservas (cancel/reschedule de outro → 404).

## O que esta tela cobre do MVP

| Já disponível | Ainda não |
|---------------|-----------|
| Login / logout do morador | Cadastro público de morador |
| Catálogo de áreas ativas | IA |
| Calendário do mês e horários do dia (ocupado × livre) | |
| Nova reserva com convidados (`/areas/<slug>/reservar/`) | |
| Detalhe, cancelar e reagendar (`/reservas/...`) | |
| Lista “Minhas reservas” (protocolo, badge, Ver / Cancelar / Reagendar) | |
| E-mail (console ou SendGrid) | |
| API REST autenticada (`/api/...`) | |
| Admin Django para gestão (`/admin/`) | |

## URLs do morador

| Método | Caminho | Nome |
|--------|---------|------|
| GET | `/` | Minhas reservas |
| GET | `/areas/` | Lista de áreas |
| GET | `/areas/<slug>/` | Calendário da área |
| GET/POST | `/areas/<slug>/reservar/` | Nova reserva |
| GET | `/reservas/<protocol>/` ou `/reservas/<id>/` | Detalhe |
| GET/POST | `/reservas/<id>/cancelar/` | Cancelar |
| GET/POST | `/reservas/<id>/reagendar/` | Reagendar (calendário GET; form GET `?start=`; POST confirma) |

## Migrations e superusuário

Com o stack no ar:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Dados de demonstração (seed)

```bash
docker compose exec web python manage.py seed_demo
```

Cria blocos, 3 espaços (Salão de Festas, Churrasqueira, Quadra), usuários acima e 2 reservas no Salão (1 futura, 1 passada) para `morador1`.

## Testes

```bash
docker compose exec web pytest
```

Cobertura relevante: conflito de horário, cancelamento dentro/fora do prazo (service e view), reagendamento livre/ocupado, morador B não cancela reserva do morador A, e-mail via console sem exceção, availability com slot confirmed indisponível, POST `/api/reservations/` autenticado, cancel API fora do prazo → 400, usuário B não cancela via API, `send_reservation_email` no created.

## Stack

| Camada        | Tecnologia                          |
|---------------|-------------------------------------|
| Backend       | Django 5 + Django REST Framework    |
| E-mail        | django-anymail + SendGrid (ou console) |
| Banco         | PostgreSQL 16                       |
| Front         | HTML, CSS (Bootstrap 5 CDN), JS vanilla (`app/static/js/guests.js`) |
| Estáticos     | WhiteNoise                          |
| Testes        | pytest-django                       |
| Deploy local  | Docker Compose                      |
| Deploy nuvem  | Render (`render.yaml` + Dockerfile) |

## Estrutura

```
config/          # projeto Django (settings, urls, wsgi, asgi)
app/             # único app da aplicação
  api/           # serializers, views e urls DRF (pacote, não é app Django)
  models/
  views/
  forms/
  services/      # reservas, availability, notifications (e-mail)
  urls/
  templates/
  static/
  tests/
```

## Variáveis de ambiente

Veja `.env.example`. O arquivo `.env` não é versionado; use-o a partir do exemplo.

Principais de e-mail:

```env
EMAIL_BACKEND=
DEFAULT_FROM_EMAIL=CondoAgenda <nao-responda@example.com>
EMAIL_API_KEY=
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
```

Produção (comentadas no `.env.example`): `DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `EMAIL_API_KEY`, `DEFAULT_FROM_EMAIL`. Superuser no boot: `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` (senha só no painel; não versionar).

## Publicação na nuvem

Item **nuvem** da ementa do **PJI240**: o CondoAgenda sobe em produção com `DEBUG=0`, estáticos via WhiteNoise, Gunicorn e Postgres gerenciado.

Plataforma documentada: **[Render](https://render.com/)** (arquivo `render.yaml` no repositório).

### 1. Criar o serviço e o Postgres

1. Faça push deste repositório para o GitHub/GitLab.
2. No Render: **New → Blueprint** e selecione o repositório (usa o `render.yaml`).
3. O Blueprint cria:
   - **Web Service** `condoagenda` (build pelo `Dockerfile`, health check em `/contas/entrar/`);
   - **Postgres** `condoagenda-db`, ligado ao web via `DATABASE_URL`.

Alternativa sem Blueprint: **New → Web Service** (Docker) + **New → PostgreSQL**, e cole as envs abaixo manualmente (`DATABASE_URL` = Internal Database URL do Postgres).

### 2. Colar as variáveis de ambiente

No painel do Web Service → **Environment** (ou quando o Blueprint pedir `sync: false`):

| Variável | Exemplo / observação |
|----------|----------------------|
| `DEBUG` | `0` (já vem no Blueprint) |
| `SECRET_KEY` | gerada pelo Blueprint, ou uma chave longa aleatória |
| `ALLOWED_HOSTS` | hostname do Render, ex.: `condoagenda.onrender.com` (obrigatório, ou o app não sobe) |
| `CSRF_TRUSTED_ORIGINS` | origem HTTPS, ex.: `https://condoagenda.onrender.com` |
| `DATABASE_URL` | injetada pelo Blueprint a partir do Postgres |
| `EMAIL_API_KEY` | chave SendGrid (opcional; sem chave o e-mail vai para o log) |
| `DEFAULT_FROM_EMAIL` | remetente verificado no provedor de e-mail |
| `DJANGO_SUPERUSER_USERNAME` | ex.: `admin` (obrigatório para criar o admin no boot) |
| `DJANGO_SUPERUSER_EMAIL` | ex.: `admin@condo.local` |
| `DJANGO_SUPERUSER_PASSWORD` | senha forte; **só no dashboard** — não versionar |

Não coloque valores secretos no repositório — só no painel da plataforma.

### 3. Superusuário no deploy (sem Shell)

Com as três `DJANGO_SUPERUSER_*` preenchidas no Environment:

- o **primeiro deploy** cria o admin via `createsuperuser --noinput` no `entrypoint.sh`;
- deploys seguintes ignoram o erro *"user already exists"* e sobem o Gunicorn normalmente;
- login em `/admin/` com esse usuário;
- blocos, áreas e moradores se cadastram pelo admin — **sem `seed_demo` em produção** (senhas de demo não devem ir para o ar).

Se a URL permanecer pública depois da banca, **troque a senha** do superusuário (ou desative o serviço).

### 4. URL pública esperada

Após o deploy: `https://<nome-do-servico>.onrender.com` (ex.: `https://condoagenda.onrender.com`).

Login do morador: `https://<nome-do-servico>.onrender.com/contas/entrar/`
Admin: `https://<nome-do-servico>.onrender.com/admin/`

### Conferir collectstatic localmente

Com o stack de desenvolvimento no ar (ou só o serviço web):

```bash
docker compose run --rm -e DEBUG=0 web python manage.py collectstatic --noinput
```

Os arquivos devem ir para `staticfiles/` (no container; com volume, também no host). Em produção o `entrypoint.sh` já roda `collectstatic --noinput` antes do Gunicorn.
