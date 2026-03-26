# -*- coding: utf-8 -*-
# Author: Matheus C. Pestana

import io
from typing import Optional

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://dadosabertos.camara.leg.br/api/v2"


# ---------------------------------------------------------------------------
# Funções auxiliares de API
# ---------------------------------------------------------------------------


def _get_paginado(endpoint: str, params: Optional[dict] = None) -> list:
    """Busca todos os resultados de um endpoint paginado."""
    params = params.copy() if params else {}
    params["itens"] = 200
    resultados = []
    pagina = 1
    while True:
        params["pagina"] = pagina
        try:
            resp = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=30)
            resp.raise_for_status()
            dados = resp.json().get("dados", [])
        except Exception as exc:
            st.error(f"Erro ao acessar {endpoint}: {exc}")
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
def get_todos_deputados() -> list[dict]:
    return _get_paginado("/deputados")


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


# ---------------------------------------------------------------------------
# Tab 1 — Frentes por Legislatura
# ---------------------------------------------------------------------------


def tab_frentes_por_legislatura():
    st.header("Frentes por Legislatura")

    with st.spinner("Carregando legislaturas..."):
        legislaturas = get_legislaturas()

    if not legislaturas:
        st.error("Não foi possível carregar as legislaturas.")
        return

    opcoes_leg = {
        f"{leg['id']} — {leg.get('dataInicio', '')[:4]} a {leg.get('dataFim', '')[:4]}": leg["id"]
        for leg in legislaturas
    }
    leg_selecionada_label = st.selectbox("Legislatura", list(opcoes_leg.keys()))
    id_legislatura = opcoes_leg[leg_selecionada_label]

    with st.spinner("Carregando frentes..."):
        frentes = get_frentes(id_legislatura)

    if not frentes:
        st.warning("Nenhuma frente encontrada para esta legislatura.")
        return

    st.caption(f"{len(frentes)} frentes encontradas.")

    palavra_chave = st.text_input("Filtrar frentes por palavra-chave")

    frentes_filtradas = frentes
    if palavra_chave.strip():
        kw = palavra_chave.strip().lower()
        frentes_filtradas = [
            f for f in frentes if kw in f.get("titulo", "").lower()
        ]

    mapa_frentes = {f["titulo"]: f["id"] for f in frentes_filtradas}

    frentes_escolhidas = st.multiselect(
        "Selecione as frentes para análise",
        options=list(mapa_frentes.keys()),
    )

    if not frentes_escolhidas:
        st.info("Selecione ao menos uma frente para gerar a matriz.")
        return

    if st.button("Gerar Matriz", key="btn_matriz"):
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

        df = pd.DataFrame(linhas).set_index("Deputado")
        st.dataframe(df, width="stretch")

        excel_bytes = df_para_excel(df)
        st.download_button(
            label="Baixar Excel",
            data=excel_bytes,
            file_name=f"frentes_legislatura_{id_legislatura}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Tab 2 — Frentes por Deputado
# ---------------------------------------------------------------------------


def tab_frentes_por_deputado():
    st.header("Frentes e Comissões por Deputado")

    with st.spinner("Carregando deputados..."):
        deputados = get_todos_deputados()

    if not deputados:
        st.error("Não foi possível carregar a lista de deputados.")
        return

    st.caption(f"{len(deputados)} deputados carregados.")

    modo = st.selectbox(
        "O que deseja buscar?",
        options=["Somente Frentes", "Somente Comissões", "Frentes e Comissões"],
        key="modo_busca",
    )

    filtro_dep = st.text_input("Filtrar deputado por nome")

    deps_filtrados = deputados
    if filtro_dep.strip():
        kw = filtro_dep.strip().lower()
        deps_filtrados = [
            d for d in deputados if kw in d.get("nome", "").lower()
        ]

    mapa_deps = {d["nome"]: d["id"] for d in deps_filtrados}

    deps_escolhidos = st.multiselect(
        "Selecione os deputados",
        options=list(mapa_deps.keys()),
    )

    if not deps_escolhidos:
        st.info("Selecione ao menos um deputado para continuar.")
        return

    buscar_frentes = modo in ("Somente Frentes", "Frentes e Comissões")
    buscar_comissoes = modo in ("Somente Comissões", "Frentes e Comissões")

    apenas_comissao_no_nome = False
    if buscar_comissoes:
        apenas_comissao_no_nome = st.checkbox(
            'Apenas com "Comissão" no nome',
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

    if st.button("Buscar", key="btn_busca_dep"):
        progresso = st.progress(0)
        linhas = []

        for i, nome_dep in enumerate(deps_escolhidos):
            id_dep = mapa_deps[nome_dep]

            frentes_dep: list[dict] = []
            orgaos_dep: list[dict] = []

            if buscar_frentes:
                with st.spinner(f"Buscando frentes de {nome_dep}..."):
                    frentes_dep = get_frentes_deputado(id_dep)

            if buscar_comissoes:
                with st.spinner(f"Buscando comissões de {nome_dep}..."):
                    orgaos_dep = _filtrar_orgaos(get_orgaos_deputado(id_dep))

            if modo == "Somente Frentes":
                for f in frentes_dep:
                    linhas.append(
                        {
                            "Deputado": nome_dep,
                            "Frente": f.get("titulo", ""),
                            "Legislatura": f.get("idLegislatura", ""),
                            "Título/Cargo na Frente": f.get("titulo", ""),
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

        df = pd.DataFrame(linhas)
        st.dataframe(df, width="stretch")

        nome_arquivo = {
            "Somente Frentes": "frentes_por_deputado.xlsx",
            "Somente Comissões": "comissoes_por_deputado.xlsx",
            "Frentes e Comissões": "frentes_comissoes_por_deputado.xlsx",
        }[modo]

        excel_bytes = df_para_excel(df.set_index("Deputado"))
        st.download_button(
            label="Baixar Excel",
            data=excel_bytes,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Frentes Parlamentares — ISER", layout="wide")
    st.title("Frentes Parlamentares")
    st.caption("Dados: API de Dados Abertos da Câmara dos Deputados | ISER")

    tab1, tab2 = st.tabs(["Frentes por Legislatura", "Frentes por Deputado"])

    with tab1:
        tab_frentes_por_legislatura()

    with tab2:
        tab_frentes_por_deputado()


if __name__ == "__main__":
    main()
