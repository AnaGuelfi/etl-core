# SAVITS ETL Core

Repositório de engenharia de dados do projeto SAVITS
(Sistema de Avaliação e Validação de Impactos em Tecnologias Sociais).

## Escopo

Este repositório concentra componentes relacionados a:

- pipelines ETL;
- preparação de datasets;
- organização de camadas de dados;
- arquitetura em modelo medalhão.

## Estrutura inicial

```text
configs/         Configurações
docs/            Documentação
src/savits_etl/  Código-fonte
tests/           Testes
```

## Ambiente de desenvolvimento

Python 3.11 ou superior.

### Criar ambiente virtual

```bash
python -m venv .venv
source .venv/Scripts/activate
```

### Instalar em modo de desenvolvimento

```bash
python -m pip install -e ".[dev]"
```
