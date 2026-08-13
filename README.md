# Sistema Web de Pedidos — Lovers Açaí

Sistema web para gerenciamento de pedidos de açaí, desenvolvido para pequenos estabelecimentos. Substitui atendimentos manuais por um fluxo digital com três painéis separados: cliente, gestor e administrador.

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Frontend | HTML, CSS, JavaScript, Nginx |
| Backend | Python, Flask, Flask-CORS |
| Banco de dados | SQLite |
| Infraestrutura | Docker, Docker Compose |
| Testes | Pytest |

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
│   ├── js/
│   │   ├── auth.js              # Helpers de login/token compartilhados
│   │   └── ...
│   └── Dockerfile
├── backend/
│   ├── back/
│   │   ├── app.py               # Entrada da aplicação Flask
│   │   ├── database.py          # Conexão e inicialização do banco
│   │   └── routes/
│   │       ├── pedidos.py       # Rotas de pedidos, pagamento manual e vendas
│   │       ├── cardapio.py      # Rotas de cardápio e complementos
│   │       └── auth.py          # Login/logout do proprietário
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_unit.py
│   │   ├── test_integracao.py
│   │   └── test_auth.py
│   ├── requirements.txt
│   └── Dockerfile
├── db/                          # Volume do banco SQLite (gerado automaticamente)
└── docker-compose.yml
```

---

## Como executar

### Pré-requisito

- [Docker](https://www.docker.com/) instalado

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
| **Gestor** | http://localhost:8081 | Receber e avançar pedidos |
| **Admin** | http://localhost:8082 | Gerenciar cardápio e complementos |
| SQLite Web | http://localhost:8083 | Visualizar banco de dados |

> Cada perfil é isolado por porta no mesmo container Nginx. Acessar uma página pelo perfil errado retorna **403**.

### Login do proprietário

Os painéis **Gestor** e **Admin** exigem login (usuário e senha ficam salvos, com a senha criptografada, na tabela `usuarios` do banco). Credenciais padrão, criadas automaticamente na primeira execução:

```
usuário: admin
senha:   acai2026
```

Para definir outras credenciais desde o início, exporte `OWNER_USUARIO` e `OWNER_SENHA` (por exemplo no `backend/.env`) **antes** de subir o projeto pela primeira vez — elas só são usadas na criação inicial do usuário. Para trocar depois, edite a tabela `usuarios` (ex.: pelo SQLite Web em http://localhost:8083).

### Páginas do cliente (porta 8080)

| Página | URL |
|---|---|
| Início | http://localhost:8080 |
| Fazer pedido | http://localhost:8080/html/pedido.html |
| Acompanhar pedidos | http://localhost:8080/html/acompanhar.html |

---

## Funcionalidades

### Cliente
- Montar pedido com produtos e acompanhamentos (máx. 4 por item)
- Acompanhar **múltiplos pedidos simultâneos** em tempo real (atualização a cada 5 segundos)
- Pedidos ativos salvos no navegador — fecha e reabre sem perder o acompanhamento
- Pedidos entregues removidos automaticamente da lista

### Gestor (login obrigatório)
- Visualizar todos os pedidos em tempo real
- Avançar status do pedido: `aguardando → confirmado → a_caminho → entregue`
- Limpar pedidos entregues

### Admin (login obrigatório)
- Cadastrar, editar e remover itens do cardápio (nome e preço)
- Cadastrar e remover complementos (acompanhamentos disponíveis)
- Alterações refletem imediatamente na página de pedido do cliente

---

## API — Backend

Base URL: `http://localhost:5000`

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
| GET 🔒 | `/pedidos` | Lista pedidos ativos (exclui os aguardando comprovante de Pix) |
| GET 🔒 | `/pedidos/pendentes` | Lista pedidos Pix aguardando confirmação de comprovante |
| GET | `/pedidos/<id>` | Busca pedido por ID (usado pelo cliente para acompanhar) |
| POST | `/pedidos` | Cria novo pedido |
| PATCH 🔒 | `/pedidos/<id>/status` | Avança status do pedido |
| PATCH 🔒 | `/pedidos/<id>/confirmar-pagamento` | Confirma manualmente o comprovante de um pedido Pix |
| GET 🔒 | `/pedidos/vendas-por-dia` | Total vendido por dia nos últimos 7 dias (só pedidos entregues) |
| DELETE 🔒 | `/pedidos/entregues` | Remove pedidos entregues |

### Cardápio

| Método | Rota | Descrição |
|---|---|---|
| GET | `/cardapio` | Lista todos os itens |
| POST 🔒 | `/cardapio` | Cria novo item |
| PUT 🔒 | `/cardapio/<id>` | Edita nome e preço |
| DELETE 🔒 | `/cardapio/<id>` | Remove item |

### Complementos

| Método | Rota | Descrição |
|---|---|---|
| GET | `/complementos` | Lista todos os complementos |
| POST 🔒 | `/complementos` | Cria novo complemento |
| DELETE 🔒 | `/complementos/<id>` | Remove complemento |

### Formas de pagamento

Não há gateway de pagamento online — as três formas (`pix`, `cartao`, `dinheiro`) são
resolvidas manualmente:

- **Pix**: o pedido nasce com status `pendente_pagamento`. O cliente paga usando uma
  chave Pix fixa exibida na tela e envia o comprovante pelo WhatsApp da loja; o gestor
  confirma manualmente no painel (`PATCH /pedidos/<id>/confirmar-pagamento`), o que move
  o pedido para `aguardando` e ele passa a aparecer na fila normal.
- **Cartão**: pago na entrega, com maquininha física. A taxa de entrega é R$5,00 quando
  os itens (sem a taxa) somam até R$50,00, ou R$3,00 acima disso. O pedido já nasce em
  `aguardando`, sem etapa de confirmação.
- **Dinheiro**: R$3,00 de taxa fixa, com campo opcional de troco. Também nasce direto em
  `aguardando`.

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
    "itens": [{"nome": "Copo 400ml Médio", "preco": 18.0, "extras": ["Granola", "Banana"], "qtd": 1}],
    "total": 18.0
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

82 testes cobrindo criação, listagem, busca, avanço de status, confirmação manual de pagamento, remoção, login/logout e casos de erro. Cada teste roda com banco isolado.

---

## Informações Acadêmicas

**Instituto Federal de Educação, Ciência e Tecnologia — Rio Grande do Sul — Campus Rolante**  
Curso Superior em Tecnologia em Análise e Desenvolvimento de Sistemas  
**Aluno:** Kauê Salazar Cardoso  
**Disciplina:** Trabalho de Conclusão de Curso (TCC)  
**Projeto:** Sistema Web de Pedidos de Açaí
