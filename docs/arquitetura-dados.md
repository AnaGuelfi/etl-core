# Arquitetura de dados

O ETL do SAVITS será organizado segundo uma arquitetura em camadas.

## Bronze

Camada destinada aos dados obtidos diretamente das fontes.

Características:

- preservação dos dados de origem;
- possibilidade de reprocessamento.

## Silver

Camada destinada aos dados tratados e padronizados.

Características:

- limpeza;
- padronização de nomes e tipos;
- tratamento de valores ausentes;
- normalização de estruturas;
- integração.

## Gold

Camada destinada aos dados preparados para consumo.

Características:

- datasets;
- agregações;
- indicadores.

## Fluxo

```text
Fontes de dados
      |
      v
    Bronze
      |
      v
    Silver
      |
      v
     Gold

