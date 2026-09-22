# CondoAgenda

Protótipo acadêmico do **PJI240** (Projeto Integrador em Computação II — Univesp).

Sistema web para consulta, reserva, reagendamento e cancelamento de áreas comuns de condomínio (salão, churrasqueira, quadra etc.), com calendário de disponibilidade, lista de convidados, e-mail de confirmação e painel da gestão.

> Etapa atual: o morador reserva horários livres, vê o protocolo em Minhas reservas, consulta o detalhe, cancela (dentro do prazo `min_cancel_hours`, padrão 48h) e reagenda para outro slot da mesma área. E-mail e API REST ficam para os próximos incrementos.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose

## Subir o projeto

Copie o arquivo de ambiente (se ainda não existir) e suba os serviços:

```bash
cp .env.example .env
docker compose up --build
```

A aplicação fica em [http://localhost:8000](http://localhost:8000). O admin Django em [http://localhost:8000/admin/](http://localhost:8000/admin/).

Na primeira subida o `entrypoint.sh` aguarda o Postgres, aplica as migrations e inicia o Gunicorn. Com `DEBUG=True` no `.env`, o Gunicorn sobe com `--reload`: alterações em Python (views, forms, etc.) são aplicadas sem `docker compose restart web`. Templates e estáticos do app também entram pelo volume `.:/app`.

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

Entrar como `morador1` → [Áreas comuns](http://localhost:8000/areas/) → abrir uma área → no calendário, escolher o dia → clicar num horário livre → preencher pessoas/convidados → Confirmar → a home [Minhas reservas](http://localhost:8000/) mostra o protocolo na message e na lista.

### Fluxo: cancelar

Em Minhas reservas (ou no detalhe), use **Cancelar** se ainda estiver dentro do prazo (`Space.min_cancel_hours`, padrão 48h antes do início). A tela pede confirmação: “Tem certeza que deseja cancelar a reserva {protocol}?”. Fora do prazo, a reserva permanece confirmada e aparece message de erro (sem 500).

### Fluxo: reagendar

Em Minhas reservas (ou no detalhe), use **Reagendar** se o status for Confirmada e o início ainda for futuro. Abre o calendário da **mesma área** (`/reservas/<id>/reagendar/`). Ao clicar num horário livre, abre o **formulário** pré-preenchido (início/fim editáveis no mesmo dia, convidados e observações). Só o POST do formulário marca a original como **Reagendada** e cria uma nova **Confirmada** (`related_reservation` + convidados novos). Slot ocupado por outra reserva devolve erro no formulário.

## O que esta tela cobre do MVP

| Já disponível | Ainda não |
|---------------|-----------|
| Login / logout do morador | Cadastro público de morador |
| Catálogo de áreas ativas | API REST e e-mail |
| Calendário do mês e horários do dia (ocupado × livre) | |
| Nova reserva com convidados (`/areas/<slug>/reservar/`) | |
| Detalhe, cancelar e reagendar (`/reservas/...`) | |
| Lista “Minhas reservas” (protocolo, badge, Ver / Cancelar / Reagendar) | |
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

Cobertura relevante: conflito de horário, cancelamento dentro/fora do prazo (service e view), reagendamento livre/ocupado, morador B não cancela reserva do morador A.

## Stack

| Camada        | Tecnologia                          |
|---------------|-------------------------------------|
| Backend       | Django 5 + Django REST Framework    |
| Banco         | PostgreSQL 16                       |
| Front         | HTML, CSS (Bootstrap 5 CDN), JS vanilla (`app/static/js/guests.js`) |
| Estáticos     | WhiteNoise                          |
| Testes        | pytest-django                       |
| Deploy local  | Docker Compose                      |

## Estrutura

```
config/          # projeto Django (settings, urls, wsgi, asgi)
app/             # único app da aplicação
  models/
  views/
  forms/
  services/
  urls/
  templates/
  static/
  tests/
```

## Variáveis de ambiente

Veja `.env.example`. O arquivo `.env` não é versionado; use-o a partir do exemplo.
