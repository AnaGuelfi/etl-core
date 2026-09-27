# Fontes de dados

As fontes utilizadas pelo ETL são registradas em `configs/sources.yml`.

## Categorias iniciais

O projeto considera inicialmente duas categorias de dados:

- patentes;
- tecnologias sociais.

## INPI

A primeira fonte implementada é a área de Dados Abertos do Instituto Nacional da
Propriedade Industrial (INPI).

O pipeline utiliza arquivos públicos de pedidos de patentes em lote e realiza o
processamento nas camadas Bronze, Silver e Gold.

Credenciais e outros dados sensíveis não devem ser armazenados no repositório.
