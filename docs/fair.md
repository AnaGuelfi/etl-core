# FAIR

A camada de dados do SAVITS foi estruturada com base nos princípios FAIR — Findable, Accessible, Interoperable e Reusable — aplicados aos pipelines ETL, aos produtos analíticos e aos datasets derivados.

## Findable — Localizáveis

Os dados são organizados em uma arquitetura de camadas Bronze, Silver e Gold, com separação entre dados coletados, dados tratados e produtos consolidados.

As principais saídas analíticas possuem caminhos estáveis e nomes definidos no projeto, incluindo:

- Gold consolidada de patentes do INPI;
- Gold consolidada de tecnologias sociais;
- datasets preparados para aprendizado de máquina;
- indicadores analíticos utilizados pelo dashboard.

Os datasets derivados para aprendizado de máquina possuem metadados contendo origem, quantidade de registros e hash SHA-256 dos arquivos utilizados e produzidos.

## Accessible — Acessíveis

Os pipelines utilizam dados provenientes de fontes públicas e mantêm informações de referência e origem sempre que disponíveis.

Os produtos processados utilizam formatos de amplo suporte, como CSV, JSON e JSONL, podendo ser utilizados por ferramentas de análise de dados, visualização e aprendizado de máquina.

A geração dos produtos é realizada por comandos reproduzíveis a partir do código versionado no repositório.

## Interoperable — Interoperáveis

Os dados são normalizados durante o processamento e consolidados em estruturas comuns.

Entre os elementos utilizados para aumentar a interoperabilidade estão:

- codificação UTF-8;
- arquivos CSV estruturados;
- JSON e JSONL para metadados e dados textuais;
- classificação IPC para patentes;
- campos tecnológicos associados à classificação tecnológica;
- identificação de ODS nas tecnologias sociais;
- padronização de nomes de campos e tipos de informação entre as fontes.

A consolidação das tecnologias sociais permite trabalhar de forma conjunta com registros provenientes de diferentes fontes.

## Reusable — Reutilizáveis

Os pipelines preservam a origem dos registros e permitem reconstruir os produtos analíticos a partir das fontes processadas.

O código de extração, transformação, consolidação, análise e preparação dos datasets é versionado no repositório.

Os datasets destinados a aprendizado de máquina são derivados das Golds oficiais e possuem metadados próprios, incluindo:

- arquivo de origem;
- hash SHA-256 da origem;
- quantidade de registros;
- relação de campos;
- hash SHA-256 do produto gerado.

Os datasets de tecnologias sociais também possuem uma representação textual em JSONL destinada a aplicações de processamento de linguagem natural e LLM.

## Reprodutibilidade

A execução do projeto é acompanhada por testes automatizados e verificações de qualidade de código.

As transformações são implementadas em código e os produtos podem ser regenerados a partir das respectivas fontes de dados, reduzindo a necessidade de tratamento manual.