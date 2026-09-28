# CantinaOS

Sistema de gerenciamento de cantina escolar desenvolvido em Django.

## Requisitos

- Python 3.11+
- pip
- virtualenv (recomendado)

## Instalação

### 1. Criar e ativar ambiente virtual

```bash
# Linux/macOS
python -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1

# Windows (cmd)
python -m venv venv
venv\Scripts\activate.bat
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

Copie o arquivo de exemplo e ajuste conforme necessário:

```bash
cp .env.example .env
```

Para desenvolvimento local, o arquivo `.env` pode ficar com os valores padrão.

### 4. Executar migrações

```bash
python manage.py migrate
```

### 5. Executar servidor de desenvolvimento

```bash
python manage.py runserver
```

Acesse: http://localhost:8000

## Estrutura do Projeto

```
cantinaos/
├── config/                 # Configurações do Django
│   ├── settings.py         # Settings unificado (dev/prod via env vars)
│   ├── urls.py             # URLs principais
│   ├── wsgi.py             # WSGI para produção
│   └── asgi.py             # ASGI para produção
├── frontend/               # App principal
│   ├── views.py            # Views (lógica de apresentação)
│   ├── mock_data.py        # Dados mockados para desenvolvimento
│   ├── urls.py             # URLs do frontend
│   └── templates/          # Templates Django
├── static/                 # Arquivos estáticos
│   ├── css/
│   │   ├── reset.css       # Reset CSS
│   │   ├── variables.css   # Design tokens (cores, espaçamento, tipografia)
│   │   ├── layout.css      # Layout principal (sidebar, header, main)
│   │   ├── components.css  # Componentes reutilizáveis
│   │   └── pages.css       # Estilos específicos por página
│   ├── js/
│   │   └── main.js         # JavaScript vanilla
│   └── favicon.svg         # Favicon
├── manage.py
├── requirements.txt        # Dependências base
├── requirements-prod.txt   # Dependências de produção
├── .env.example            # Exemplo de variáveis de ambiente
└── .gitignore
```

## Variáveis de Ambiente

| Variável | Descrição | Padrão (Dev) | Obrigatória em Prod |
|----------|-----------|--------------|---------------------|
| `DJANGO_DEBUG` | Ativa modo debug | `True` | Não (deve ser `False`) |
| `DJANGO_SECRET_KEY` | Chave secreta do Django | `django-insecure-...` | **Sim** |
| `ALLOWED_HOSTS` | Hosts permitidos (CSV) | `localhost,127.0.0.1,0.0.0.0` | **Sim** |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para CSRF (CSV) | - | **Sim** |
| `DATABASE_URL` | URL do banco (PostgreSQL) | - | Não* |
| `DB_ENGINE` | Engine do banco | `django.db.backends.sqlite3` | Não* |
| `DB_NAME` | Nome do banco | - | Não* |
| `DB_USER` | Usuário do banco | - | Não* |
| `DB_PASSWORD` | Senha do banco | - | Não* |
| `DB_HOST` | Host do banco | - | Não* |
| `DB_PORT` | Porta do banco | - | Não* |
| `EMAIL_HOST` | Servidor SMTP | - | Não |
| `EMAIL_PORT` | Porta SMTP | `587` | Não |
| `EMAIL_USE_TLS` | Usar TLS | `True` | Não |
| `EMAIL_HOST_USER` | Usuário SMTP | - | Não |
| `EMAIL_HOST_PASSWORD` | Senha SMTP | - | Não |
| `DEFAULT_FROM_EMAIL` | Email remetente padrão | - | Não |

\* Para PostgreSQL em produção, use `DATABASE_URL` OU as variáveis `DB_*` individuais.

## Desenvolvimento vs Produção

### Desenvolvimento
```bash
# Usa SQLite, DEBUG=True, console email
python manage.py runserver
```

### Produção
Configure as variáveis de ambiente obrigatórias e use um servidor WSGI:

```bash
# Exemplo com gunicorn
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY="sua-chave-secreta-de-50-chars"
export ALLOWED_HOSTS="seudominio.com,www.seudominio.com"
export CSRF_TRUSTED_ORIGINS="https://seudominio.com,https://www.seudominio.com"
export DATABASE_URL="postgres://user:pass@host:5432/dbname"
# ... outras variáveis ...

gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Ou use o ASGI com uvicorn/daphne:
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

## Arquivos Estáticos em Produção

```bash
# Coleta arquivos estáticos
python manage.py collectstatic --noinput

# Sirva via nginx/Apache ou CDN
# Configure STATIC_ROOT no servidor web
```

## Banco de Dados

### Desenvolvimento (SQLite)
Padrão, não requer configuração adicional.

### Produção (PostgreSQL)
Recomendado para produção. Configure via `DATABASE_URL` ou variáveis `DB_*`.

```bash
# Exemplo DATABASE_URL
postgres://usuario:senha@host:5432/nome_do_banco
```

## Preparação para AWS

O projeto está preparado para deploy em AWS:

1. **Elastic Beanstalk / EC2 / ECS**: Use `gunicorn` (WSGI) ou `uvicorn` (ASGI)
2. **RDS PostgreSQL**: Configure via `DATABASE_URL`
3. **S3 + CloudFront**: Para arquivos estáticos/media (configure `STATICFILES_STORAGE` customizado)
4. **ALB/NLB**: Terminação SSL no load balancer
5. **Secrets Manager / Parameter Store**: Para `DJANGO_SECRET_KEY`, credenciais de banco, etc.

## Comandos Úteis

```bash
# Verificar configuração
python manage.py check
python manage.py check --deploy

# Criar superusuário
python manage.py createsuperuser

# Coletar estáticos
python manage.py collectstatic

# Shell Django
python manage.py shell

# Testes
python manage.py test
```

## Tecnologias

- **Backend**: Django 4.2+
- **Frontend**: Django Templates + CSS próprio + JavaScript vanilla
- **Banco Dev**: SQLite
- **Banco Prod**: PostgreSQL
- **Servidor Dev**: `runserver`
- **Servidor Prod**: Gunicorn (WSGI) / Uvicorn (ASGI)

## Licença

Projeto interno - CantinaOS