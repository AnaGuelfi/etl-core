import json
from collections.abc import Iterator

from savits_etl.transforms.transforma import (
    extrair_tecnologia,
    gerar_silver_transforma,
)

HTML_EXEMPLO = """
<html>
    <section>
        <div class="socialtecnology-detail-header">
            <h1>
                <span>Tecnologia Exemplo</span>
            </h1>

            <div>
                <small>
                    <i class="fas fa-medal"></i>
                </small>

                <small>Certificada</small>
                <small>2024</small>
            </div>

            <div>
                <a
                    href="https://transforma.fbb.org.br/tecnologia-social/tema/educacao"
                >
                    <small>Educação</small>
                </a>

                <a
                    href="https://transforma.fbb.org.br/tecnologia-social/tema/renda"
                >
                    <small>Renda</small>
                </a>
            </div>
        </div>
    </section>

    <h3>Resumo</h3>
    <div class="text-muted alter ts-detail-plain">
        Resumo da tecnologia.
    </div>

    <h3>Objetivo</h3>
    <div class="text-muted alter ts-detail-plain">
        Objetivo da tecnologia.
    </div>

    <h3>Objetivos específicos</h3>
    <div class="text-muted alter ts-detail-plain">
        Objetivo específico um.
    </div>

    <h3>Problema Solucionado</h3>
    <div class="text-muted alter ts-detail-plain">
        Problema solucionado.
    </div>

    <h3>Descrição</h3>
    <div class="text-muted alter ts-detail-plain">
        Descrição da tecnologia.
    </div>

    <h3>Recursos Necessários</h3>
    <div class="text-muted alter ts-detail-plain">
        Recursos necessários.
    </div>

    <h3>Resultados Alcançados</h3>
    <div class="text-muted alter ts-detail-plain">
        Resultados alcançados.
    </div>

    <h3>Público atendido</h3>
    <ul class="list-unstyled text-muted alter ts-detail-audience mb-0">
        <li class="ts-detail-audience-item">
            Adulto
        </li>
        <li class="ts-detail-audience-item">
            Jovens
        </li>
    </ul>

    <a
        href="https://transforma.fbb.org.br/tecnologia-social/ods/educacao-de-qualidade"
        title="Educação de Qualidade"
    >
        <img src="ods-4.png">
    </a>

    <a
        href="https://transforma.fbb.org.br/perfil/instituicao/instituicao-exemplo"
    >
        <code>Instituição Exemplo</code>
    </a>
</html>
"""


def test_extrair_tecnologia() -> None:
    row = {
        "slug": "tecnologia-exemplo",
        "source_url": (
            "https://transforma.fbb.org.br/"
            "tecnologia-social/"
            "tecnologia-exemplo"
        ),
        "listing_page": "1",
        "html": HTML_EXEMPLO,
    }

    (
        technology,
        themes,
        ods,
        publics,
    ) = extrair_tecnologia(row)

    assert (
        technology["titulo"]
        == "Tecnologia Exemplo"
    )

    assert (
        technology["instituicao"]
        == "Instituição Exemplo"
    )

    assert (
        technology["status_premio"]
        == "Certificada"
    )

    assert (
        technology["ano_premio"]
        == "2024"
    )

    assert (
        technology["resumo"]
        == "Resumo da tecnologia."
    )

    assert (
        technology["objetivo"]
        == "Objetivo da tecnologia."
    )

    assert (
        technology[
            "objetivos_especificos"
        ]
        == "Objetivo específico um."
    )

    assert (
        technology["publico_atendido"]
        == "Adulto; Jovens"
    )

    assert [
        row["tema"]
        for row in themes
    ] == [
        "Educação",
        "Renda",
    ]

    assert ods == [
        {
            "slug": "tecnologia-exemplo",
            "ods": "Educação de Qualidade",
            "ods_url": (
                "https://transforma.fbb.org.br/"
                "tecnologia-social/ods/"
                "educacao-de-qualidade"
            ),
        }
    ]

    assert publics == [
        {
            "slug": "tecnologia-exemplo",
            "publico": "Adulto",
        },
        {
            "slug": "tecnologia-exemplo",
            "publico": "Jovens",
        },
    ]


class _FakeSource:
    def read(
        self,
        reference: int,
        **kwargs: str,
    ) -> Iterator[dict[str, str]]:
        del reference
        del kwargs

        yield {
            "slug": "tecnologia-exemplo",
            "source_url": (
                "https://transforma.fbb.org.br/"
                "tecnologia-social/"
                "tecnologia-exemplo"
            ),
            "listing_page": "1",
            "html": HTML_EXEMPLO,
        }


def test_gerar_silver_transforma(
    tmp_path,
) -> None:
    (
        technologies_path,
        themes_path,
        ods_path,
        publics_path,
        metadata_path,
    ) = gerar_silver_transforma(
        reference=20260927,
        source=_FakeSource(),
        silver_root=tmp_path,
    )

    assert technologies_path.exists()
    assert themes_path.exists()
    assert ods_path.exists()
    assert publics_path.exists()
    assert metadata_path.exists()

    with metadata_path.open(
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    assert (
        metadata["datasets"]
        ["tecnologias"]
        ["records"]
        == 1
    )

    assert (
        metadata["datasets"]
        ["tecnologias"]
        ["unique_slugs"]
        == 1
    )

    assert (
        metadata["datasets"]
        ["tecnologias"]
        ["with_publico_atendido"]
        == 1
    )

    assert (
        metadata["datasets"]
        ["temas"]
        ["records"]
        == 2
    )

    assert (
        metadata["datasets"]
        ["ods"]
        ["records"]
        == 1
    )

    assert (
        metadata["datasets"]
        ["publicos"]
        ["records"]
        == 2
    )