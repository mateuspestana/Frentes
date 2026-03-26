# Frentes Parlamentares — ISER

Aplicação Streamlit para exploração e exportação de dados sobre frentes parlamentares da Câmara dos Deputados, desenvolvida para o ISER.

Os dados são obtidos em tempo real pela [API de Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br/api/v2).

---

## Funcionalidades

### Aba 1 — Frentes por Legislatura

- Seleciona uma legislatura disponível
- Filtra frentes por palavra-chave no nome
- Permite escolher múltiplas frentes para análise
- Gera uma **matriz** onde:
  - **Linhas** = deputados membros de ao menos uma frente selecionada
  - **Colunas** = frentes selecionadas
  - **Célula** = cargo do deputado na frente (ex: "Presidente", "Coordenador"), `Sim` se for membro sem cargo específico, ou vazio se não participar
- Exporta a matriz em Excel

### Aba 2 — Frentes por Deputado

- Filtra e seleciona um ou mais deputados por nome
- Busca todas as frentes das quais cada deputado selecionado faz parte
- Exibe tabela com: Deputado, Frente, Legislatura e Título/Cargo
- Exporta a tabela em Excel

---

## Como executar

Com o ambiente conda `Quaerite` ativo:

```bash
conda activate Quaerite
streamlit run app_frentes.py
```

Ou diretamente:

```bash
conda run -n Quaerite streamlit run app_frentes.py
```

O app estará disponível em `http://localhost:8501`.

---

## Dependências

Listadas em `requirements.txt`:

| Pacote      | Versão mínima |
|-------------|--------------|
| streamlit   | 1.21.0       |
| pandas      | 1.5.3        |
| requests    | 2.28.2       |
| openpyxl    | 3.1.2        |

---

## Estrutura

```
Frentes/
├── app_frentes.py   # Aplicação principal
├── requirements.txt # Dependências
└── README.md        # Este arquivo
```

---

## Fonte dos dados

API de Dados Abertos da Câmara dos Deputados  
`https://dadosabertos.camara.leg.br/api/v2`

Endpoints utilizados:
- `GET /legislaturas`
- `GET /frentes`
- `GET /frentes/{id}/membros`
- `GET /deputados`
- `GET /deputados/{id}/frentes`
