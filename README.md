# Sistema Web de Pedidos — Lovers Açaí

Sistema web para gerenciamento de pedidos de açaí, desenvolvido para pequenos estabelecimentos. Substitui atendimentos manuais por um fluxo digital com três painéis separados: cliente, gestor e administrador.

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Frontend | HTML, CSS, JavaScript, Nginx |
| Backend | Python, Flask, Flask-CORS |
| Banco de dados | PostgreSQL |
| IA | Gemini (chatbot de atendimento ao cliente) |
| Notificações | Web Push (VAPID) |
| Infraestrutura local | Docker, Docker Compose |
| Testes | Pytest |

---

## Deploy (produção)

| Camada | Onde está hospedado |
|---|---|
| Frontend | [Netlify](https://www.netlify.com/) — `netlify.toml` publica a pasta `frontend/`, deploy automático a cada push no `main` |
| Backend | [Google Cloud Run](https://cloud.google.com/run) — build a partir de `backend/Dockerfile`, deploy automático via GitHub Actions (`.github/workflows/deploy-backend.yml`) a cada push no `main` que toque em `backend/` |
| Banco de dados | [Neon](https://neon.tech/) — PostgreSQL serverless, conectado via `DATABASE_URL` |

Segredos do backend (`DATABASE_URL`, `GEMINI_API_KEY`, `VAPID_PRIVATE_KEY`) ficam no Secret Manager do Google Cloud, não no repositório. O serviço roda com `--max-instances=3` e um alerta de orçamento configurado na conta de faturamento. A autenticação do GitHub Actions com o Google Cloud usa Workload Identity Federation (sem chave de service account armazenada).

Localmente, o `docker-compose.yml` sobe um PostgreSQL próprio (container `tcc_acai_postgres`) para desenvolvimento — não é necessário depender do Neon para rodar o projeto na sua máquina.

---

## Arquitetura

```
TCC/
├── frontend/
│   ├── html/
│   │   ├── index.html           # Página inicial (cliente)
│   │   ├── pedido.html          # Montagem de pedido (cliente)
│   │   ├── acompanhar.html      # Acompanhamento de pedidos (cliente)
│   │   ├── login.html           # Login do proprietário
│   │   ├── estabelecimento.html # Painel do gestor (porta 8081) — exige login
│   │   └── admin.html           # Painel do admin (porta 8082) — exige login
│   ├── css/
│   ├── img/                     # Fotos usadas na home
│   ├── js/
│   │   ├── auth.js              # Helpers de login/token compartilhados
│   │   ├── chat.js              # Widget do chat com IA
│   │   └── ...
│   ├── sw.js                    # Service worker (push notifications)
│   └── Dockerfile
├── backend/
│   ├── back/
│   │   ├── app.py               # Entrada da aplicação Flask
│   │   ├── database.py          # Conexão PostgreSQL e inicialização/migração do schema
│   │   ├── horario.py           # Regras de horário de atendimento
│   │   ├── push.py              # Envio de notificações Web Push
│   │   ├── chatbot_gemini.py    # Lógica do chatbot (tools + loop do Gemini)
│   │   └── routes/
│   │       ├── pedidos.py       # Pedidos, confirmação de pagamento e histórico de vendas
│   │       ├── cardapio.py      # Cardápio e complementos (com categorias)
│   │       ├── auth.py          # Login/logout do proprietário
│   │       ├── horario.py       # Rotas de horário de atendimento
│   │       ├── chatbot.py       # Rota do chat com IA
│   │       └── push.py          # Inscrição para notificações push
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── db/
│   └── init/                    # Script SQL de inicialização do Postgres local (docker-compose)
├── docker-compose.yml
└── netlify.toml                 # Config de deploy do frontend (Netlify)
```

---

## Como executar localmente

### Pré-requisito

- [Docker](https://www.docker.com/) instalado

### Variáveis de ambiente

Crie `backend/.env` (gitignored, nunca commitado) com:

```
GEMINI_API_KEY=<chave da API Gemini, para o chatbot>
VAPID_PRIVATE_KEY=<chave privada VAPID>
VAPID_PUBLIC_KEY=<chave pública VAPID>
VAPID_CONTATO=mailto:seu-email@exemplo.com
```

`DATABASE_URL` não precisa entrar no `.env` local — o `docker-compose.yml` já aponta para o Postgres do próprio container. Em produção (Cloud Run), `DATABASE_URL` fica no Secret Manager, apontando para o banco no Neon.

### Subir o projeto

```bash
docker compose up --build -d
```

### Encerrar

```bash
docker compose down
```

---

## Acesso

| Perfil | URL | Descrição |
|---|---|---|
| **Cliente** | http://localhost:8080 | Fazer e acompanhar pedidos |
| **Gestor** | http://localhost:8081 | Receber, avançar e confirmar pedidos |
| **Admin** | http://localhost:8082 | Gerenciar cardápio, complementos e horário |
| Adminer | http://localhost:8083 | Visualizar/gerenciar o banco PostgreSQL |

> Cada perfil é isolado por porta no mesmo container Nginx. Acessar uma página pelo perfil errado retorna **403**.

### Login do proprietário

Os painéis **Gestor** e **Admin** exigem login (usuário e senha ficam salvos, com a senha criptografada, na tabela `usuarios` do banco). Credenciais padrão, criadas automaticamente na primeira execução:

```
usuário: admin
senha:   acai2026
```

Para definir outras credenciais desde o início, exporte `OWNER_USUARIO` e `OWNER_SENHA` (por exemplo no `backend/.env`) **antes** de subir o projeto pela primeira vez — elas só são usadas na criação inicial do usuário. Para trocar depois, edite a tabela `usuarios` (ex.: pelo Adminer em http://localhost:8083).

### Páginas do cliente (porta 8080)

| Página | URL |
|---|---|
| Início | http://localhost:8080 |
| Fazer pedido | http://localhost:8080/html/pedido.html |
| Acompanhar pedidos | http://localhost:8080/html/acompanhar.html |

---

## Funcionalidades

### Cliente
- Montar pedido com produtos (agrupados em categorias: Açaí Tradicional, Cupuaçu, Iogurte Grego, Iogurte Grego com Morango) e complementos (Calda, Frutas, Complementos Gratuitos, Complementos Adicionais), sem limite de escolhas
- Pagamento via Pix (chave estática, confirmação manual) ou cartão (maquininha na entrega, taxa própria)
- Campo opcional de observação no pedido
- Acompanhar **múltiplos pedidos simultâneos** em tempo real (atualização a cada 5 segundos)
- Pedidos ativos salvos no navegador — fecha e reabre sem perder o acompanhamento
- Pedidos entregues removidos automaticamente da lista
- Chat com IA (Gemini) para dúvidas sobre cardápio, horário e até fechar pedidos pela conversa
- Horário de atendimento exibido dinamicamente

### Gestor (login obrigatório)
- Visualizar todos os pedidos em tempo real, com notificação push de pedido novo
- Confirmar manualmente o comprovante de pedidos Pix (fila separada de "aguardando comprovante")
- Avançar status do pedido: `aguardando → confirmado → a_caminho → entregue`
- Avisar o cliente por WhatsApp a cada mudança de status
- Histórico de vendas dos últimos 7 dias
- Limpar pedidos entregues

### Admin (login obrigatório)
- Cadastrar, editar e remover itens do cardápio e complementos (nome, preço e categoria)
- Definir horário de atendimento por dia da semana
- Alterações refletem imediatamente na página de pedido do cliente

---

## API — Backend

Base URL local: `http://localhost:5000` · Base URL produção: `https://acai-express-backend-738933484701.us-east1.run.app`

Rotas marcadas com 🔒 exigem o cabeçalho `Authorization: Bearer <token>`, obtido em `/login`.

### Autenticação

| Método | Rota | Descrição |
|---|---|---|
| POST | `/login` | Autentica com `{usuario, senha}` e retorna `{token}` |
| POST | `/logout` | Invalida o token enviado |

### Pedidos

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Health check |
| GET | `/config` | Retorna a chave pública VAPID para o frontend |
| GET 🔒 | `/pedidos` | Lista pedidos ativos (exclui os aguardando comprovante de Pix) |
| GET 🔒 | `/pedidos/pendentes` | Lista pedidos Pix aguardando confirmação de comprovante |
| GET | `/pedidos/<id>` | Busca pedido por ID (usado pelo cliente para acompanhar) |
| POST | `/pedidos` | Cria novo pedido |
| PATCH 🔒 | `/pedidos/<id>/status` | Avança status do pedido |
| PATCH 🔒 | `/pedidos/<id>/confirmar-pagamento` | Confirma manualmente o comprovante de um pedido Pix |
| GET 🔒 | `/pedidos/vendas-por-dia` | Total vendido por dia nos últimos 7 dias (só pedidos entregues) |
| DELETE 🔒 | `/pedidos/entregues` | Tira os pedidos entregues da fila do gestor (arquiva — não apaga, então o histórico de vendas continua contando eles) |

### Cardápio e complementos

| Método | Rota | Descrição |
|---|---|---|
| GET | `/cardapio` | Lista todos os itens (com categoria) |
| POST 🔒 | `/cardapio` | Cria novo item |
| PUT 🔒 | `/cardapio/<id>` | Edita nome, preço e categoria |
| DELETE 🔒 | `/cardapio/<id>` | Remove item |
| GET | `/complementos` | Lista todos os complementos (com categoria) |
| POST 🔒 | `/complementos` | Cria novo complemento |
| PUT 🔒 | `/complementos/<id>` | Edita nome, preço e categoria |
| DELETE 🔒 | `/complementos/<id>` | Remove complemento |

### Horário de atendimento

| Método | Rota | Descrição |
|---|---|---|
| GET | `/horario` | Lista horário de todos os dias da semana |
| PUT 🔒 | `/horario/<dia>` | Edita horário/fechamento de um dia |

### Chat com IA e notificações

| Método | Rota | Descrição |
|---|---|---|
| POST | `/chatbot/mensagem` | Envia mensagem ao chatbot (Gemini) e recebe resposta |
| POST 🔒 | `/push/subscribe` | Registra inscrição de notificação push do gestor |

### Formas de pagamento

Não há gateway de pagamento online — as três formas (`pix`, `cartao`, `dinheiro`) são resolvidas manualmente. A taxa de entrega é sempre R$3,00; o cartão tem uma **taxa de maquininha separada**, somada em cima da taxa de entrega:

- **Pix**: o pedido nasce com status `pendente_pagamento`. O cliente paga usando uma chave Pix fixa exibida na tela e envia o comprovante pelo WhatsApp da loja; o gestor confirma manualmente no painel (`PATCH /pedidos/<id>/confirmar-pagamento`), o que move o pedido para `aguardando` e ele passa a aparecer na fila normal.
- **Cartão**: pago na entrega, com maquininha física. Além da taxa de entrega (R$3,00), a maquininha cobra R$2,00 quando os itens (sem taxas) somam até R$50,00, ou R$3,00 quando somam mais que isso. O pedido já nasce em `aguardando`, sem etapa de confirmação.
- **Dinheiro**: taxa de entrega R$3,00, com campo opcional de troco. Também nasce direto em `aguardando`.

### Fluxo de status

```
aguardando → confirmado → a_caminho → entregue
```

### Exemplo de criação de pedido

```bash
curl -X POST http://localhost:5000/pedidos \
  -H "Content-Type: application/json" \
  -d '{
    "cliente": {"nome": "João", "tel": "51999999999", "end": "Rua das Flores, 10 — Centro, Rolante"},
    "itens": [{"nome": "Copo 330ml Açaí Tradicional", "preco": 19.0, "extras": ["Granola", "Banana"], "qtd": 1}],
    "total": 22.0,
    "forma_pagamento": "dinheiro"
  }'
```

---

## Testes

Com o projeto rodando:

```bash
docker compose exec backend python -m pytest tests/ -v
```

Ou sem o projeto em execução (container descartável):

```bash
docker compose run --rm backend python -m pytest tests/ -v
```

92 testes cobrindo criação, listagem, busca, avanço de status, confirmação manual de pagamento, categorias de cardápio/complementos, remoção, login/logout e casos de erro. Cada teste roda com banco isolado.

---

## Informações Acadêmicas

**Instituto Federal de Educação, Ciência e Tecnologia — Rio Grande do Sul — Campus Rolante**  
Curso Superior em Tecnologia em Análise e Desenvolvimento de Sistemas  
**Aluno:** Kauê Salazar Cardoso  
**Disciplina:** Trabalho de Conclusão de Curso (TCC)  
**Projeto:** Sistema Web de Pedidos de Açaí
