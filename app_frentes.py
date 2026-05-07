# -*- coding: utf-8 -*-
# Author: Matheus C. Pestana

import io
import time
from typing import Optional

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://dadosabertos.camara.leg.br/api/v2"


# ---------------------------------------------------------------------------
# Funções auxiliares de API
# ---------------------------------------------------------------------------


def _get_paginado(
    endpoint: str,
    params: Optional[dict] = None,
    itens_por_pagina: int = 200,
    tentativas: int = 3,
) -> list:
    """Busca todos os resultados de um endpoint paginado."""
    params = params.copy() if params else {}
    params["itens"] = itens_por_pagina
    resultados = []
    pagina = 1
    while True:
        params["pagina"] = pagina
        dados = []
        ultimo_erro = None
        for tentativa in range(1, tentativas + 1):
            try:
                resp = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=30)
                resp.raise_for_status()
                dados = resp.json().get("dados", [])
                ultimo_erro = None
                break
            except Exception as exc:
                ultimo_erro = exc
                if tentativa < tentativas:
                    # Pequeno backoff para reduzir erros transitórios (ex.: 504).
                    time.sleep(0.8 * tentativa)
        if ultimo_erro is not None:
            if resultados:
                st.warning(
                    f"Falha ao carregar a página {pagina} de {endpoint}. "
                    "Os resultados exibidos são parciais devido a instabilidade da API."
                )
                break
            st.error(f"Erro ao acessar {endpoint}: {ultimo_erro}")
            break
        if not dados:
            break
        resultados.extend(dados)
        pagina += 1
    return resultados


@st.cache_data(show_spinner=False)
def get_legislaturas() -> list[dict]:
    dados = _get_paginado("/legislaturas")
    return sorted(dados, key=lambda x: x.get("id", 0), reverse=True)


@st.cache_data(show_spinner=False)
def get_frentes(id_legislatura: int) -> list[dict]:
    return _get_paginado("/frentes", {"idLegislatura": id_legislatura})


@st.cache_data(show_spinner=False)
def get_frentes_recentes(id_legislatura: Optional[int] = None) -> list[dict]:
    params = {"idLegislatura": id_legislatura} if id_legislatura else None
    dados = _get_paginado("/frentes", params)
    return sorted(dados, key=lambda x: x.get("id", 0), reverse=True)


@st.cache_data(show_spinner=False)
def get_membros_frente(id_frente: int) -> list[dict]:
    try:
        resp = requests.get(
            f"{API_BASE}/frentes/{id_frente}/membros", timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("dados", [])
    except Exception as exc:
        st.error(f"Erro ao buscar membros da frente {id_frente}: {exc}")
        return []


@st.cache_data(show_spinner=False)
def get_titulo_cargo_na_frente(id_deputado: int, id_frente: int) -> str:
    membros = get_membros_frente(id_frente)
    for membro in membros:
        if membro.get("id") == id_deputado:
            titulo = (membro.get("titulo") or "").strip()
            return titulo if titulo else "Membro"
    return ""


@st.cache_data(show_spinner=False, ttl=86400)
def get_todos_deputados(id_legislatura: Optional[int] = None) -> list[dict]:
    params = {}
    if id_legislatura is not None:
        params["idLegislatura"] = id_legislatura
    return _get_paginado("/deputados", params, itens_por_pagina=100)


@st.cache_data(show_spinner=False)
def get_frentes_deputado(id_deputado: int) -> list[dict]:
    try:
        resp = requests.get(
            f"{API_BASE}/deputados/{id_deputado}/frentes", timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("dados", [])
    except Exception as exc:
        st.error(f"Erro ao buscar frentes do deputado {id_deputado}: {exc}")
        return []


@st.cache_data(show_spinner=False)
def get_orgaos_deputado(id_deputado: int) -> list[dict]:
    try:
        resp = requests.get(
            f"{API_BASE}/deputados/{id_deputado}/orgaos",
            params={"itens": 200},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("dados", [])
    except Exception as exc:
        st.error(f"Erro ao buscar comissões do deputado {id_deputado}: {exc}")
        return []


# ---------------------------------------------------------------------------
# Utilitário de exportação
# ---------------------------------------------------------------------------


def df_para_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=True)
    return buffer.getvalue()


def render_contexto():
    st.markdown(
        """
        ### Sobre esta plataforma
        Esta aplicação organiza dados públicos da Câmara dos Deputados para mapear conexões
        entre parlamentares, frentes e comissões em diferentes legislaturas, combinando uma
        leitura estrutural das redes de participação com um monitoramento público de frentes
        recentes. Ao observar deputados que compartilham as mesmas frentes,
        frentes com composições parcialmente semelhantes e parlamentares que ocupam posições
        simultâneas em múltiplas arenas, torna-se possível identificar padrões de aproximação
        política, circulação de agendas e potenciais núcleos de coordenação temática. Em termos
        analíticos, o app permite investigar como vínculos institucionais aparentemente dispersos
        podem convergir na prática legislativa, inclusive quando atores distintos se conectam por causas comuns
        em campos como religião, segurança pública, saúde, meio ambiente e direitos sociais.
        """
    )
    st.caption("Fonte dos dados: API de Dados Abertos da Câmara dos Deputados.")


def render_rodape():
    st.divider()
    st.markdown(
        """
        **Autoria:** Matheus C. Pestana | [Plataforma Religião e Poder](https://religiaoepoder.org.br) | [ISER (Instituto de Estudos da Religião)](https://iser.org.br)
        """
    )


# ---------------------------------------------------------------------------
# Tab 1 — Frentes por Legislatura
# ---------------------------------------------------------------------------


def tab_frentes_por_legislatura():
    st.header("Frentes por Legislatura")
    st.caption(
        "Selecione uma legislatura, escolha frentes de interesse e gere uma matriz para identificar sobreposições de participação."
    )

    with st.container(border=True):
        with st.spinner("Carregando legislaturas..."):
            legislaturas = get_legislaturas()

        if not legislaturas:
            st.error("Não foi possível carregar as legislaturas.")
            return

        opcoes_leg = {
            f"{leg['id']} — {leg.get('dataInicio', '')[:4]} a {leg.get('dataFim', '')[:4]}": leg["id"]
            for leg in legislaturas
        }
        leg_selecionada_label = st.selectbox("1) Legislatura", list(opcoes_leg.keys()))
        id_legislatura = opcoes_leg[leg_selecionada_label]

        with st.spinner("Carregando frentes..."):
            frentes = get_frentes(id_legislatura)

        if not frentes:
            st.warning("Nenhuma frente encontrada para esta legislatura.")
            return

        st.caption(f"{len(frentes)} frentes encontradas.")

        palavra_chave = st.text_input("2) Filtrar frentes por palavra-chave")

        frentes_filtradas = frentes
        if palavra_chave.strip():
            kw = palavra_chave.strip().lower()
            frentes_filtradas = [
                f for f in frentes if kw in f.get("titulo", "").lower()
            ]

        mapa_frentes = {f["titulo"]: f["id"] for f in frentes_filtradas}

        frentes_escolhidas = st.multiselect(
            "3) Selecione as frentes para análise",
            options=list(mapa_frentes.keys()),
            help="A matriz será montada com os deputados que aparecem em pelo menos uma frente selecionada.",
        )

        if not frentes_escolhidas:
            st.info("Selecione ao menos uma frente para gerar a matriz.")
            return

    if st.button("4) Gerar Matriz", key="btn_matriz", type="primary"):
        dados_membros: dict[str, dict[int, str]] = {}
        _membros_raw: dict[str, list[dict]] = {}

        progresso = st.progress(0)
        for i, titulo_frente in enumerate(frentes_escolhidas):
            id_frente = mapa_frentes[titulo_frente]
            with st.spinner(f"Buscando membros: {titulo_frente}..."):
                membros = get_membros_frente(id_frente)
            _membros_raw[titulo_frente] = membros
            dados_membros[titulo_frente] = {}
            for m in membros:
                id_dep = m.get("id")
                titulo_cargo = (m.get("titulo") or "").strip()
                dados_membros[titulo_frente][id_dep] = titulo_cargo if titulo_cargo else "Sim"
            progresso.progress((i + 1) / len(frentes_escolhidas))

        # mapa_nomes é construído a partir dos próprios membros retornados pela API
        # (cada membro já traz o campo "nome"), evitando dependência de /deputados
        # que só cobre a legislatura atual
        mapa_nomes: dict[int, str] = {}
        for frente_membros_raw in _membros_raw.values():
            for m in frente_membros_raw:
                dep_id = m.get("id")
                dep_nome = (m.get("nome") or "").strip()
                if dep_id and dep_nome:
                    mapa_nomes[dep_id] = dep_nome

        todos_ids = set()
        for frente_membros in dados_membros.values():
            todos_ids.update(frente_membros.keys())

        linhas = []
        for id_dep in sorted(todos_ids):
            nome = mapa_nomes.get(id_dep, f"ID {id_dep}")
            linha = {"Deputado": nome}
            for titulo_frente in frentes_escolhidas:
                linha[titulo_frente] = dados_membros[titulo_frente].get(id_dep, "")
            linhas.append(linha)

        if not linhas:
            st.warning("Nenhum membro encontrado para as frentes selecionadas.")
            return

        st.success("Matriz gerada com sucesso.")
        df = pd.DataFrame(linhas).set_index("Deputado")
        st.dataframe(df, width="stretch")
        st.caption(
            "Leitura da matriz: células com texto indicam participação; quando houver cargo formal, ele aparece no lugar de 'Sim'."
        )

        excel_bytes = df_para_excel(df)
        st.download_button(
            label="Baixar Excel da Matriz",
            data=excel_bytes,
            file_name=f"frentes_legislatura_{id_legislatura}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Tab 2 — Frentes por Deputado
# ---------------------------------------------------------------------------


def tab_frentes_por_deputado():
    st.header("Frentes e Comissões por Deputado")
    st.caption(
        "Analise trajetórias individuais para comparar vínculos simultâneos entre frentes parlamentares e comissões."
    )

    with st.container(border=True):
        with st.spinner("Carregando legislaturas..."):
            legislaturas = get_legislaturas()

        if not legislaturas:
            st.error("Não foi possível carregar as legislaturas.")
            return

        opcoes_leg = {
            f"{leg['id']} — {leg.get('dataInicio', '')[:4]} a {leg.get('dataFim', '')[:4]}": leg["id"]
            for leg in legislaturas
        }
        leg_label = st.selectbox(
            "1) Legislatura",
            list(opcoes_leg.keys()),
            key="leg_dep",
            help="Selecionar uma legislatura lista todos os parlamentares que exerceram mandato nela, incluindo suplentes e quem já saiu.",
        )
        id_legislatura_dep = opcoes_leg[leg_label]

        with st.spinner("Carregando deputados..."):
            deputados = get_todos_deputados(id_legislatura=id_legislatura_dep)

        if not deputados:
            st.error("Não foi possível carregar a lista de deputados.")
            return

        st.caption(f"{len(deputados)} parlamentares encontrados para esta legislatura.")

        modo = st.selectbox(
            "2) O que deseja buscar?",
            options=["Somente Frentes", "Somente Comissões", "Frentes e Comissões"],
            key="modo_busca",
            help="Use o modo combinado para observar possíveis convergências entre arenas parlamentares.",
        )

        filtro_dep = st.text_input("3) Filtrar deputado por nome")

        deps_filtrados = deputados
        if filtro_dep.strip():
            kw = filtro_dep.strip().lower()
            deps_filtrados = [
                d for d in deputados if kw in d.get("nome", "").lower()
            ]

        mapa_deps = {d["nome"]: d["id"] for d in deps_filtrados}

        deps_escolhidos = st.multiselect(
            "4) Selecione os deputados",
            options=list(mapa_deps.keys()),
        )

        if not deps_escolhidos:
            st.info("Selecione ao menos um deputado para continuar.")
            return

        buscar_frentes = modo in ("Somente Frentes", "Frentes e Comissões")
        buscar_comissoes = modo in ("Somente Comissões", "Frentes e Comissões")
        incluir_frentes_anteriores = False
        if buscar_frentes:
            incluir_frentes_anteriores = st.checkbox(
                "5) Incluir frentes do mesmo deputado em legislaturas anteriores",
                value=False,
                key="frentes_anteriores",
                help="Quando desativado, os resultados de frentes ficam restritos à legislatura selecionada.",
            )

        buscar_cargo_detalhado = False
        if modo == "Somente Frentes":
            buscar_cargo_detalhado = st.checkbox(
                "6) Buscar título/cargo detalhado na frente (mais lento)",
                value=False,
                key="cargo_detalhado_frente",
                help="Quando desativado, a coluna de cargo será preenchida como 'Membro' para acelerar a consulta.",
            )

        apenas_comissao_no_nome = False
        if buscar_comissoes:
            apenas_comissao_no_nome = st.checkbox(
                '7) Apenas com "Comissão" no nome',
                key="filtro_comissao_nome",
            )

    def _filtrar_orgaos(orgaos: list[dict]) -> list[dict]:
        if not apenas_comissao_no_nome:
            return orgaos
        return [
            o for o in orgaos
            if "comissão" in (o.get("nomeOrgao") or "").lower()
            or "comissao" in (o.get("nomeOrgao") or "").lower()
        ]

    if st.button("8) Buscar", key="btn_busca_dep", type="primary"):
        progresso = st.progress(0)
        linhas = []

        for i, nome_dep in enumerate(deps_escolhidos):
            id_dep = mapa_deps[nome_dep]

            frentes_dep: list[dict] = []
            orgaos_dep: list[dict] = []

            if buscar_frentes:
                with st.spinner(f"Buscando frentes de {nome_dep}..."):
                    frentes_raw = get_frentes_deputado(id_dep)
                    if incluir_frentes_anteriores:
                        frentes_dep = [
                            f
                            for f in frentes_raw
                            if int(f.get("idLegislatura", 0)) <= id_legislatura_dep
                        ]
                    else:
                        frentes_dep = [
                            f
                            for f in frentes_raw
                            if int(f.get("idLegislatura", 0)) == id_legislatura_dep
                        ]

            if buscar_comissoes:
                with st.spinner(f"Buscando comissões de {nome_dep}..."):
                    orgaos_dep = _filtrar_orgaos(get_orgaos_deputado(id_dep))

            if modo == "Somente Frentes":
                for f in frentes_dep:
                    id_frente = f.get("id")
                    cargo_frente = "Membro"
                    if buscar_cargo_detalhado and id_frente is not None:
                        cargo_frente = get_titulo_cargo_na_frente(id_dep, id_frente)
                    linhas.append(
                        {
                            "Deputado": nome_dep,
                            "Frente": f.get("titulo", ""),
                            "Legislatura": f.get("idLegislatura", ""),
                            "Título/Cargo na Frente": cargo_frente,
                        }
                    )

            elif modo == "Somente Comissões":
                for o in orgaos_dep:
                    linhas.append(
                        {
                            "Deputado": nome_dep,
                            "Comissão": o.get("nomeOrgao", o.get("siglaOrgao", "")),
                            "Sigla": o.get("siglaOrgao", ""),
                            "Cargo": o.get("cargo", ""),
                            "Início": o.get("dataInicio", ""),
                            "Fim": o.get("dataFim", ""),
                        }
                    )

            else:  # Frentes e Comissões — uma linha por deputado
                frentes_str = " /// ".join(
                    f.get("titulo", "") for f in frentes_dep if f.get("titulo")
                )
                comissoes_str = " /// ".join(
                    o.get("nomeOrgao", o.get("siglaOrgao", ""))
                    for o in orgaos_dep
                    if o.get("nomeOrgao") or o.get("siglaOrgao")
                )
                linhas.append(
                    {
                        "Deputado": nome_dep,
                        "Frentes": frentes_str,
                        "Comissões": comissoes_str,
                    }
                )

            progresso.progress((i + 1) / len(deps_escolhidos))

        if not linhas:
            st.warning("Nenhum resultado encontrado para os deputados selecionados.")
            return

        st.success("Consulta concluída com sucesso.")
        df = pd.DataFrame(linhas)
        st.dataframe(df, width="stretch")
        st.caption(
            "Interpretação: sobreposição entre frentes e comissões pode indicar coordenação temática entre parlamentares em diferentes arenas."
        )

        nome_arquivo = {
            "Somente Frentes": "frentes_por_deputado.xlsx",
            "Somente Comissões": "comissoes_por_deputado.xlsx",
            "Frentes e Comissões": "frentes_comissoes_por_deputado.xlsx",
        }[modo]

        excel_bytes = df_para_excel(df.set_index("Deputado"))
        st.download_button(
            label="Baixar Excel dos Resultados",
            data=excel_bytes,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def tab_frentes_recentes():
    st.header("Últimas Frentes Criadas")
    st.caption(
        "A API da Câmara não expõe a data de criação da frente neste endpoint; por isso, usamos o ID em ordem decrescente como aproximação de recência. Assim, não temos de forma automática a possibilidade de exibir a data de criação das frentes."
    )

    with st.spinner("Carregando legislaturas..."):
        legislaturas = get_legislaturas()

    if not legislaturas:
        st.error("Não foi possível carregar as legislaturas.")
        return

    opcoes_leg = {"Todas as legislaturas": None}
    opcoes_leg.update(
        {
            f"{leg['id']} — {leg.get('dataInicio', '')[:4]} a {leg.get('dataFim', '')[:4]}": leg["id"]
            for leg in legislaturas
        }
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        leg_label = st.selectbox(
            "Filtrar por legislatura (opcional)",
            list(opcoes_leg.keys()),
            key="leg_recentes",
        )
    with col2:
        limite = st.number_input(
            "Quantidade",
            min_value=5,
            max_value=50,
            value=10,
            step=1,
            key="limite_recentes",
        )

    id_leg = opcoes_leg[leg_label]
    with st.spinner("Carregando frentes mais recentes..."):
        frentes_ordenadas = get_frentes_recentes(id_legislatura=id_leg)

    if not frentes_ordenadas:
        st.warning("Nenhuma frente encontrada para o filtro selecionado.")
        return

    df = pd.DataFrame(frentes_ordenadas[: int(limite)])
    if "uri" in df.columns:
        df = df.drop(columns=["uri"])
    df = df.rename(
        columns={
            "id": "ID da Frente",
            "titulo": "Título",
            "idLegislatura": "Legislatura",
        }
    )
    st.dataframe(df, width="stretch")

    excel_bytes = df_para_excel(df.set_index("ID da Frente"))
    st.download_button(
        label="Baixar Excel das Frentes Recentes",
        data=excel_bytes,
        file_name="frentes_recentes_proxy_id.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Atlas das Frentes Parlamentares — ISER", layout="wide")
    st.title("Atlas das Frentes Parlamentares")
    st.caption(
        "Análise de conexões parlamentares a partir de dados públicos da Câmara dos Deputados."
    )
    render_contexto()

    tab1, tab2, tab3 = st.tabs(
        ["Frentes por Legislatura", "Frentes e Comissões por Deputado", "Últimas Frentes"]
    )

    with tab1:
        tab_frentes_por_legislatura()

    with tab2:
        tab_frentes_por_deputado()

    with tab3:
        tab_frentes_recentes()

    render_rodape()


if __name__ == "__main__":
    main()
