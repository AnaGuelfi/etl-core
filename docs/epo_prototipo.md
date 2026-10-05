# Integração experimental com EPO OPS

## Status

Este módulo constitui uma prova de conceito para enriquecimento dos
dados de patentes do INPI com informações bibliográficas provenientes
da European Patent Office Open Patent Services (EPO OPS).

A integração foi tecnicamente validada, incluindo:

- autenticação OAuth;
- adaptação de números de pedidos INPI para identificadores EPODOC;
- consultas bibliográficas individuais e em lote;
- tratamento de pedidos modernos e legados;
- armazenamento de respostas XML na camada Bronze;
- transformação de registros bibliográficos;
- identificação de famílias, publicações, títulos, resumos,
  depositantes, inventores, prioridades e classificações;
- mecanismos de retomada e tratamento de falhas;
- testes automatizados.

## Decisão arquitetural

A integração EPO não é utilizada como dependência do pipeline de
produção do SAVITS.

A utilização de um serviço externo sujeito a restrições operacionais,
controle de uso e variações de disponibilidade dificulta a execução
integral e reprodutível de uma coleta de grande escala.

Por esse motivo, a base analítica oficial de patentes utiliza o INPI
como fonte primária e autônoma.

O módulo EPO permanece no repositório como implementação experimental
e referência para futuras estratégias de enriquecimento.

## Pipeline de produção

INPI -> Bronze -> Silver -> Gold

## Pipeline experimental

INPI -> adaptação EPODOC -> EPO OPS -> enriquecimento experimental

Dados EPO obtidos em execuções experimentais não são necessários para
a geração da Gold oficial de patentes.
