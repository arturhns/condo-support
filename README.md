# CondoAgenda

Protótipo acadêmico do **PJI240** (Projeto Integrador em Computação II — Univesp).

Sistema web para consulta, reserva, reagendamento e cancelamento de áreas comuns de condomínio (salão, churrasqueira, quadra etc.), com calendário de disponibilidade, lista de convidados, e-mail de confirmação e painel da gestão.

**Bloco** = agrupamento de unidades (torre, bloco, ala ou setor). Cadastro de blocos neste momento só pelo admin (staff).

> Etapa atual: autenticação do morador + catálogo de áreas comuns + lista de minhas reservas. Calendário JS, criar/cancelar/reagendar, e-mail e API REST ficam para os próximos incrementos.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose

## Subir o projeto

Copie o arquivo de ambiente (se ainda não existir) e suba os serviços:

```bash
cp .env.example .env
docker compose up --build
```

A aplicação fica em [http://localhost:8000](http://localhost:8000). O admin Django em [http://localhost:8000/admin/](http://localhost:8000/admin/).

Na primeira subida o `entrypoint.sh` aguarda o Postgres, aplica as migrations e inicia o Gunicorn.

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

Fluxo típico: entrar como `morador1` → [Áreas comuns](http://localhost:8000/areas/) → detalhe do Salão de Festas → [Minhas reservas](http://localhost:8000/).

## O que esta tela cobre do MVP

| Já disponível | Ainda não |
|---------------|-----------|
| Login / logout do morador | Calendário de horários (JS) |
| Catálogo de áreas ativas | Criar reserva |
| Detalhe da área (dados + botão Reservar desabilitado) | Cancelar / reagendar |
| Lista “Minhas reservas” (protocolo, área, início, fim, status) | Cadastro público de morador |
| Admin Django para gestão (`/admin/`) | API REST e e-mail |

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

## Stack

| Camada        | Tecnologia                          |
|---------------|-------------------------------------|
| Backend       | Django 5 + Django REST Framework    |
| Banco         | PostgreSQL 16                       |
| Front         | HTML, CSS (Bootstrap 5 CDN), JS vanilla (próximos incrementos) |
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
