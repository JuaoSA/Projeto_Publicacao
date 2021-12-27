

import requests
from lxml import etree
from bs4 import BeautifulSoup
import streamlit as st
import numpy as np
from scholarly import scholarly
import subprocess
import sys
import semanticscholar as sch
import re
import time
from fuzzywuzzy import process
from fuzzywuzzy import fuzz
import texthero as hero
from texthero import preprocessing
import rdflib
from rdflib.graph import Graph
from rdflib import URIRef, BNode, Literal
from rdflib import Namespace
from rdflib.namespace import CSVW, DC, DCAT, DCTERMS, DOAP, FOAF, ODRL2, ORG, OWL, PROF, PROV, RDF, RDFS, SDO, SH, SKOS, \
    SOSA, SSN, TIME, VOID, XMLNS, XSD
from rdflib.plugins import sparql
import owlrl
from SPARQLWrapper import SPARQLWrapper, JSON, XML, N3, TURTLE, JSONLD
import unicodedata
import json
import pandas as pd
import time


@st.cache()
def busca(autor):
    dados = []
    search_query = scholarly.search_author(autor)
    for x in search_query:
        dados.append(scholarly.fill(x, sections=['basics', 'indices',
                                                 'publications']))
    return dados


@st.cache()
def busca_index(autor, dados):
    for sub in range(len(dados)):
        if dados[sub]['name'] == autor:
            return sub


def busca_data(id_autor, id_obra):
    dados = []
    URL = \
        'https://scholar.google.com.br/citations?view_op=view_citation&hl=pt-BR&user=' \
        + id_autor + '&citation_for_view=' + id_obra
    response = requests.get(URL)
    soup = BeautifulSoup(response.content, 'lxml')
    selector = soup.find_all('div', class_='gsc_oci_field')
    reviews_selector = soup.find_all('div', class_='gsc_oci_value')
    try:
        x = re.search("^(\d{4})", reviews_selector[1].text)
        if x:
            y = re.search("^(\d{4})", reviews_selector[1].text)
            dados.append(y.group())
        else:
            dados.append('NAN')
    except:
        dados.append('NAN')
    return dados


def busca_veiculo(id_autor, id_obra):
    dados = []
    URL = \
        'https://scholar.google.com.br/citations?view_op=view_citation&hl=pt-BR&user=' \
        + id_autor + '&citation_for_view=' + id_obra

    response = requests.get(URL)
    soup = BeautifulSoup(response.content, 'lxml')
    selector = soup.find_all('div', class_='gsc_oci_field')
    reviews_selector = soup.find_all('div', class_='gsc_oci_value')

    try:
        tipo = selector[2].text
        if tipo == 'Publicações' or tipo == 'Fonte' or tipo == 'Editora' or tipo == 'Livro' or tipo == 'Fonte' or tipo == 'Conferência':
            dados.append(tipo)
            dados.append(reviews_selector[2].text)
        else:
            dados.append('NAN')
            dados.append('NAN')
    except:
        dados.append('NAN')
        dados.append('NAN')
    return dados


def insere_dados_autor(posicao, dados):
    Autor = {}
    Autor = {
        'name': dados[posicao]['name'],
        'interests': dados[posicao]['interests'],
        'affiliation': dados[posicao]['affiliation'],
        'citedby': dados[posicao]['citedby'],
        'scholar_id': dados[posicao]['scholar_id'],
        'hindex': dados[posicao]['hindex'],
        'i10index': dados[posicao]['i10index'],
        'publications': [],
    }
    for x in range(len(dados[posicao]['publications'])):

        autor = dados[posicao]['scholar_id']
        obra = dados[posicao]['publications'][x]['author_pub_id']
        if len(dados[posicao]['publications'][x]['bib']) <= 1:
            data = busca_data(autor, obra)
            veiculo = busca_veiculo(autor, obra)
            Autor['publications'].append({
                'author_pub_id': obra,
                'title': dados[posicao]['publications'][x]['bib']['title'],
                'pub_year': data[0],
                'tipo_publi': veiculo[0],
                'veiculo': veiculo[1],
            })
        else:

            veiculo = busca_veiculo(autor, obra)

            Autor['publications'].append({
                'author_pub_id': obra,
                'title': dados[posicao]['publications'][x]['bib']['title'],
                'pub_year': dados[posicao]['publications'][x]['bib']['pub_year'],
                'tipo_publi': veiculo[0],
                'veiculo': veiculo[1],
            })
    return Autor


def busca_autor_semantic(position, dados):
    if_contains_t = dados[position]['publications'][position]['bib']['title']
    url = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search?query=" + if_contains_t + "&fields=title,authors")
    text = url.text
    data = json.loads(text)
    titulo = []
    nome = []
    if_contains_aut = dados[position]['name']

    for t in range(len(data['data'])):
        titulo.append(data['data'][t]['title'])
        match = process.extract(if_contains_t, titulo,
                                scorer=fuzz.token_sort_ratio)
    for x in range(len(match)):
        if match[x][1] >= 100:
            for y in range(len(data['data'][x]['authors'])):
                nome.append(data['data'][x]['authors'][y]['name'])
            match2 = process.extractOne(if_contains_aut, nome,
                                        scorer=fuzz.token_sort_ratio)
            id = data['data'][x]['authors'][y]['authorId']

        return sch.author(id, timeout=2)


def insere_dados(posicao, dados):
    autor_G = insere_dados_autor(posicao, dados)
    autor_S = busca_autor_semantic(posicao, dados)
    base_principal = autor_G
    d1 = []
    for x in range(len(dados[posicao]['publications'])):
        d1.append(dados[posicao]['publications'][x]['bib']['title'])
    d2 = []
    for x in range(len(autor_S['papers'])):
        d2.append(autor_S['papers'][x]['title'])
    match = []
    match2 = []
    for i in d2:
        match2.append(process.extractOne(i, d1,
                                         scorer=fuzz.token_sort_ratio))
    for x in range(len(match2)):
        if match2[x][1] >= 100:
            paperid = str(autor_S['papers'][x]['paperId'])
            paper = sch.paper(paperid)
            base_principal['publications'].append({
                'author_pub_id': paper['paperId'],
                'title': paper['title'],
                'pub_year': paper['year'],
                'veiculo': paper['venue'],
            })

    periodicos_link = \
        'https://docs.google.com/spreadsheets/d/e/2PACX-1vTeZuJpry8wjDWn5KBMmWpl0JAEh20SQXZ8SUzswKpwEUHuFB4-4vKIsY238K4uNJga3bRChPIKYTka/pubhtml'
    res = requests.get(periodicos_link)
    soup = BeautifulSoup(res.content, 'lxml')
    periodicos = pd.read_html(str(soup))
    d = {'inss': periodicos[0]['Unnamed: 1'],
         'periodicos': periodicos[0]['Unnamed: 2'],
         'Qualis_Final': periodicos[0]['Unnamed: 6']}
    pr = pd.DataFrame(data=d)

    conferencia_link = \
        'https://docs.google.com/spreadsheets/d/e/2PACX-1vTZsntDnttAWGHA8NZRvdvK5A_FgOAQ_tPMzP7UUf-CHwF_3PHMj_TImyXN2Q_Tmcqm2MqVknpHPoT2/pubhtml?gid=0&single=true'
    res = requests.get(conferencia_link)
    soup = BeautifulSoup(res.content, 'lxml')
    conferencias = pd.read_html(str(soup))
    c = {'sigla': conferencias[0]['Unnamed: 1'],
         'conferencia': conferencias[0]['Unnamed: 2'],
         'Qualis_Final': conferencias[0]['Unnamed: 7']}
    cn = pd.DataFrame(data=c)

    cn = pd.DataFrame(data=c).dropna()
    pr = pd.DataFrame(data=d).dropna()

    cn = cn.drop(0)
    pr = pr.drop(0)
    custom_pipeline = [preprocessing.fillna, preprocessing.lowercase,
                       preprocessing.remove_whitespace,
                       preprocessing.remove_punctuation]
    cn['conferencia_limpo'] = hero.clean(cn['conferencia'],
                                         custom_pipeline)
    pr['periodicos_limpo'] = hero.clean(pr['periodicos'],
                                        custom_pipeline)

    for i in base_principal['publications']:
        peri = process.extractOne(str(i['veiculo']),
                                  pr['periodicos'],
                                  scorer=fuzz.token_sort_ratio)
        if peri[1] >= 90:
            i['Qualis'] = str(pr['Qualis_Final'].values[peri[2]])
            i[' veiculo'] = str(pr['periodicos'].values[peri[2]])
            i['inss'] = str(pr['inss'].values[peri[2]])
            i['tipo_evento'] = 'periodico'

    for i in base_principal['publications']:
        conf = process.extractOne(str(i['veiculo']),
                                  cn['conferencia'],
                                  scorer=fuzz.token_sort_ratio)
        if conf[1] >= 90:
            i['Qualis'] = str(cn['Qualis_Final'].values[conf[2]])
            i[' veiculo'] = str(cn['conferencia'].values[conf[2]])
            i['sigla'] = str(cn['sigla'].values[conf[2]])
            i['tipo_evento'] = 'conferencia'

    return base_principal


def clear_char(palavra):
    # Unicode normalize transforma um caracter em seu equivalente em latin.
    nfkd = unicodedata.normalize('NFKD', palavra)
    palavraSemAcento = u"".join([c for c in nfkd if not unicodedata.combining(c)])

    # Usa expressão regular para retornar a palavra apenas com números, letras e espaço
    return re.sub('[^a-zA-Z0-9 \\\]', '', palavraSemAcento)


def gera_ontologia(base_principal):
    dic = {}
    p = []
    e = []
    g = Graph()
    n3data = """@prefix : <http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#> .
  @prefix owl: <http://www.w3.org/2002/07/owl#> .
  @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
  @prefix xml: <http://www.w3.org/XML/1998/namespace> .
  @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
  @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
  @base <http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao> .

  <http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao> rdf:type owl:Ontology .

  #################################################################
  #    Object Properties
  #################################################################

  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Afiliado
  :Afiliado rdf:type owl:ObjectProperty ;
            rdfs:domain :Autor_Cientifico ;
            rdfs:range :Instituicao .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Classificada
  :Classificada rdf:type owl:ObjectProperty ;
                rdfs:domain :Veiculo ;
                rdfs:range :Qualis .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Detem
  :Detem rdf:type owl:ObjectProperty ;
        rdfs:domain :Autor_Cientifico ;
        rdfs:range :Autoria_Cientifica .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Pesquisa
  :Pesquisa rdf:type owl:ObjectProperty ;
            rdfs:domain :Autor_Cientifico ;
            rdfs:range :Area_Pesquisa .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Publicado_em
  :Publicado_em rdf:type owl:ObjectProperty ;
                rdfs:domain :Publicacao ;
                rdfs:range :Veiculo .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Refere_se
  :Refere_se rdf:type owl:ObjectProperty ;
            rdfs:domain :Autoria_Cientifica ;
            rdfs:range :Texto_Autoral_Cientifico_Publicado .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Submetido
  :Submetido rdf:type owl:ObjectProperty ;
            rdfs:domain :Texto_Autoral_Cientifico_Publicado ;
            rdfs:range :Publicacao .


  #################################################################
  #    Data properties
  #################################################################

  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Area_Pesquisa
  :Area_Pesquisa rdf:type owl:DatatypeProperty ;
                rdfs:domain :Area_Pesquisa .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Autor_Citacao
  :Autor_Citacao rdf:type owl:DatatypeProperty ;
                rdfs:domain :Autor_Cientifico .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Autor_IndiceH
  :Autor_IndiceH rdf:type owl:DatatypeProperty ;
                rdfs:domain :Autor_Cientifico .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Autor_indiceI10
  :Autor_indiceI10 rdf:type owl:DatatypeProperty ;
                  rdfs:domain :Autor_Cientifico .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Edicao_Ano
  :Edicao_Ano rdf:type owl:DatatypeProperty ;
              rdfs:domain :Veiculo .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Edicao_Nome
  :Edicao_Nome rdf:type owl:DatatypeProperty ;
              rdfs:domain :Veiculo .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Edicao_Tipo
  :Edicao_Tipo rdf:type owl:DatatypeProperty ;
              rdfs:domain :Veiculo .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Instituicao
  :Instituicao rdf:type owl:DatatypeProperty ;
              rdfs:domain :Instituicao .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Nome_Autor
  :Nome_Autor rdf:type owl:DatatypeProperty ;
              rdfs:domain :Autor_Cientifico .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Publicacao_Citacao
  :Publicacao_Citacao rdf:type owl:DatatypeProperty ;
                      rdfs:domain :Publicacao .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Qualis_Extrato
  :Qualis_Extrato rdf:type owl:DatatypeProperty ;
                  rdfs:domain :Qualis .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Titulo_Artigo
  :Titulo_Artigo rdf:type owl:DatatypeProperty ;
                rdfs:domain :Texto .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Veiculo_Codigo
  :Veiculo_Codigo rdf:type owl:DatatypeProperty ;
                  rdfs:domain :Veiculo .


  #################################################################
  #    Classes
  #################################################################

  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Area_Pesquisa
  :Area_Pesquisa rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Autor_Cientifico
  :Autor_Cientifico rdf:type owl:Class ;
                    rdfs:subClassOf :Pessoa .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Autoria_Cientifica
  :Autoria_Cientifica rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Instituicao
  :Instituicao rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Pessoa
  :Pessoa rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Publicacao
  :Publicacao rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Qualis
  :Qualis rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Texto
  :Texto rdf:type owl:Class .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Texto_Autoral_Cientifico_Publicado
  :Texto_Autoral_Cientifico_Publicado rdf:type owl:Class ;
                                      rdfs:subClassOf :Texto .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#Veiculo
  :Veiculo rdf:type owl:Class .


  #################################################################
  #    Individuals
  #################################################################

  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#A1
  :A1 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "A1" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#A2
  :A2 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "A2" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#A3
  :A3 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "A3" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#A4
  :A4 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "A4" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#B1
  :B1 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "B1" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#B2
  :B2 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "B2" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#B3
  :B3 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "B3" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#B4
  :B4 rdf:type owl:NamedIndividual ,
              :Qualis ;
      :Qualis_Extrato "B4" .


  ###  http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#C
  :C rdf:type owl:NamedIndividual ,
              :Qualis ;
    :Qualis_Extrato "C" .


  ###  Generated by the OWL API (version 4.5.9.2019-02-01T07:24:44Z) https://github.com/owlcs/owlapi


  """

    ontologia = g.parse(data=n3data, format='ttl')
    pp = Namespace("http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#")  # iri
    g.bind("pp", pp)
    nome_autor = base_principal['name']
    Interesses_autor = base_principal['interests']
    Afiliação_autor = base_principal['affiliation']
    nome_autor_limpo = re.sub('[,|\s]+', '_', clear_char(nome_autor))
    Afiliacao_autor_limpo = re.sub('[,|\s]+', '_', clear_char(Afiliação_autor))

    # dados do autor
    g.add((pp[nome_autor_limpo], RDF.type, pp.Autor_Cientifico))
    g.add((pp[nome_autor_limpo], pp.Nome_Autor, Literal(base_principal['name'])))
    g.add((pp[nome_autor_limpo], pp.Autor_Citacao, Literal(base_principal['citedby'])))
    g.add((pp[nome_autor_limpo], pp.Autor_IndiceH, Literal(base_principal['hindex'])))
    g.add((pp[nome_autor_limpo], pp.Autor_indiceI10, Literal(base_principal['i10index'])))

    g.add((pp[Afiliacao_autor_limpo], RDF.type, pp.Instituicao))
    g.add((pp[Afiliacao_autor_limpo], pp.Instituicao, Literal(Afiliação_autor)))

    g.add((pp[nome_autor_limpo], pp.Afiliado, pp[Afiliacao_autor_limpo]))

    # area de interesse
    for x in Interesses_autor:
        area = re.sub('[,|\s]+', '_', clear_char(x))

        g.add((pp[area], RDF.type, pp.Area_Pesquisa))
        g.add((pp[area], pp.Area_Pesquisa, Literal(x)))
        g.add((pp[nome_autor_limpo], pp.Pesquisa, pp[area]))

    # publicacao
    for x in range(len(base_principal['publications'])):

        titulo = base_principal['publications'][x]['title']
        titulo_clean = re.sub('[,|\s]+', '_', clear_char(titulo))
        veiculo = base_principal['publications'][x]['veiculo']
        veiculo_clean = re.sub('[,|\s]+', '_', clear_char(veiculo))
        autoria = nome_autor_limpo + '_Autoria_' + str(x)
        publicacao = nome_autor_limpo + '_Publicacao_' + str(x)

        # Cria Autoria
        g.add((pp[autoria], RDF.type, pp.Autoria_Cientifica))
        g.add((pp[nome_autor_limpo], pp.Detem, pp[autoria]))

        # Cria Artigo
        g.add((pp[titulo_clean], RDF.type, pp.Texto_Autoral_Cientifico_Publicado))
        g.add((pp[titulo_clean], pp.Titulo_Artigo, Literal(titulo)))

        g.add((pp[autoria], pp.Refere_se, pp[titulo_clean]))
        # Cria Publicacao
        g.add((pp[publicacao], RDF.type, pp.Publicacao))
        g.add((pp[titulo_clean], pp.Submetido, pp[publicacao]))
        g.add((pp[veiculo_clean], RDF.type, pp.Veiculo))
        g.add((pp[veiculo_clean], pp.Edicao_Ano, Literal(base_principal['publications'][x]['pub_year'])))
        g.add((pp[veiculo_clean], pp.Edicao_Nome, Literal(veiculo)))
        g.add((pp[publicacao], pp.Publicado_em, pp[veiculo_clean]))

        if 'Qualis' in base_principal['publications'][x]:
            qualis = base_principal['publications'][x]['Qualis']
            # qualis_clear = re.sub('[,|\s]+', '_', clear_char(qualis))
            g.add((pp[veiculo_clean], pp.Classificada, pp[qualis]))
            g.add((pp[veiculo_clean], pp.Edicao_Tipo, Literal(base_principal['publications'][x]['tipo_evento'])))

    # g.serialize(data = ontologia, format='turtle')
    qres = g.query(
        """SELECT ?titulo ?q ?evento ?tipo
        WHERE
          { 
            ?x pp:Refere_se ?artigo.  
            ?artigo pp:Submetido ?y;
                pp:Titulo_Artigo ?titulo.
            ?y pp:Publicado_em  ?z.
            ?z  a pp:Veiculo;
                pp:Edicao_Nome ?evento;
                pp:Edicao_Tipo ?tipo. 
            ?z pp:Classificada ?qualis.
            ?qualis  a pp:Qualis;
                pp:Qualis_Extrato ?q.
    
    
            }""")
    # Colocar filtro por nome.
    for row in qres:
        d = {
            'titulo': re.search("([^']*)", str(row.titulo)).string,
            'evento': re.search("([^']*)", str(row.evento)).string,
            'tipo': re.search("([^']*)", str(row.tipo)).string,
            'Qualis': re.search("([^']*)", str(row.q)).string, }
        p.append(d)
    for x in range(len(p)):
        if p[x]['tipo'] == 'periodico':
            if p[x]['Qualis'] == 'A1':
                p[x]['Pontuacao'] = 1.000

            if p[x]['Qualis'] == 'A2':
                p[x]['Pontuacao'] = 0.875

            if p[x]['Qualis'] == 'A3':
                p[x]['Pontuacao'] = 0.750

            if p[x]['Qualis'] == 'A4':
                p[x]['Pontuacao'] = 0.625

            if p[x]['Qualis'] == 'B1':
                p[x]['Pontuacao'] = 0.500

            if p[x]['Qualis'] == 'B2':
                p[x]['Pontuacao'] = 0.200

            if p[x]['Qualis'] == 'B3':
                d['Pontuacao'] = 0.100

            if p[x]['Qualis'] == 'B4':
                p[x]['Pontuacao'] = 0.050
        if p[x]['tipo'] == 'conferencia':
            if p[x]['Qualis'] == 'A1':
                p[x]['Pontuacao'] = 1.000

            if p[x]['Qualis'] == 'A2':
                p[x]['Pontuacao'] = 0.875

            if p[x]['Qualis'] == 'A3':
                p[x]['Pontuacao'] = 0.750

            if p[x]['Qualis'] == 'A4':
                p[x]['Pontuacao'] = 0.625

            if p[x]['Qualis'] == 'B1':
                p[x]['Pontuacao'] = 0.500

            if p[x]['Qualis'] == 'B2':
                p[x]['Pontuacao'] = 0.200

            if p[x]['Qualis'] == 'B3':
                p[x]['Pontuacao'] = 0.100

            if p[x]['Qualis'] == 'B4':
                p[x]['Pontuacao'] = 0.050

    data_qualis = pd.DataFrame(data=p)
    return data_qualis


def main():
    dados = []
    autor_name = []
    st.title('Ontologia de Publicacao')

    selected = st.sidebar.text_input('', 'Nome Autor')
    dados = busca(selected)
    for x in range(len(dados)):
        autor_name.append(dados[x]['name'])
    escolha = st.sidebar.selectbox('Autores', autor_name)
    if st.sidebar.button('Buscar'):
        res = busca_index(escolha, dados)
        base = insere_dados(res, dados)
        tabela = gera_ontologia(base)
        st.title(base['name'])
        st.text('Afiliação:)
        st.text(base['affiliation'])
        st.text('Interesses: ')
        st.text(base['interests'])
        st.text('Total Publicações: ')
        st.text(len(base['publications']))
        st.text('Citado por: ')
        st.text(base['citedby'])

        st.dataframe(tabela)


main()