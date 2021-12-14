import streamlit as st
import requests
from lxml import etree
from bs4 import BeautifulSoup
import numpy as np
from scholarly import scholarly
import semanticscholar as sch
import pandas as pd
import re
from texthero import preprocessing
import texthero as hero

import time
from fuzzywuzzy import process
from fuzzywuzzy import fuzz
from texthero import preprocessing
import rdflib
from rdflib.graph import Graph
from rdflib import URIRef, BNode, Literal
from rdflib import Namespace
from rdflib.namespace import CSVW, DC, DCAT, DCTERMS, DOAP, FOAF, ODRL2, ORG, OWL, PROF, PROV, RDF, RDFS, SDO, SH, SKOS, SOSA, SSN, TIME, VOID, XMLNS, XSD
from rdflib.plugins import sparql
import owlrl
from SPARQLWrapper import SPARQLWrapper, JSON, XML, N3, TURTLE, JSONLD
import unicodedata
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


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

    webpage = parsing(URL)
    soup = BeautifulSoup(webpage.page_source, 'lxml')
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

    webpage = parsing(URL)

    soup = BeautifulSoup(webpage.page_source, 'lxml')
    selector = soup.find_all('div', class_='gsc_oci_field')
    reviews_selector = soup.find_all('div', class_='gsc_oci_value')

    try:
        tipo = selector[2].text
        if tipo == 'Publica\xc3\xa7\xc3\xb5es' or tipo == 'Fonte' \
            or tipo == 'Editora' or tipo == 'Livro' or tipo == 'Fonte' \
            or tipo == 'Confer\xc3\xaancia':
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
                'title': dados[posicao]['publications'][x]['bib'
                        ]['title'],
                'pub_year': data[0],
                'tipo_publi': veiculo[0],
                'veiculo': veiculo[1],
                })
        else:

            veiculo = busca_veiculo(autor, obra)

            Autor['publications'].append({
                'author_pub_id': obra,
                'title': dados[posicao]['publications'][x]['bib'
                        ]['title'],
                'pub_year': dados[posicao]['publications'][x]['bib'
                        ]['pub_year'],
                'tipo_publi': veiculo[0],
                'veiculo': veiculo[1],
                })
    return Autor


def parsing(url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    wd = webdriver.Chrome(chrome_options=options)
    wd.set_page_load_timeout(300)
    wd.get(url)
    time.sleep(5)
    return wd


def busca_autor_semantic(position, dados):
    url = parsing('https://www.semanticscholar.org/')
    buscar = url.find_element(By.CLASS_NAME, 'legacy__input ')
    buscar.send_keys(dados[position]['publications'][position]['bib'
                     ]['title'])
    buscar.submit()
    if_contains = dados[position]['name']
    time.sleep(3)
    art = url.find_element(By.CLASS_NAME, 'cl-paper-row ')
    time.sleep(3)
    aut = art.find_element(By.CLASS_NAME, 'cl-paper-authors')
    time.sleep(3)
    teste = aut.find_elements(By.CLASS_NAME,
                              'cl-paper-authors__author-link')
    match = process.extractOne(if_contains, teste,
                               scorer=fuzz.token_sort_ratio)
    url = match[0].get_attribute('href')
    id_aut = re.search("([0-9]\d+)| ", url)
    return sch.author(id_aut.group(), timeout=2)


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
        if match2[x][1] <= 80:
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
                                  pr['periodicos_limpo'],
                                  scorer=fuzz.token_sort_ratio)
        if peri[1] >= 90:
            i['Qualis'] = str(pr['Qualis_Final'].values[peri[2]])
            i[' veiculo'] = str(pr['periodicos'].values[peri[2]])
            i['inss'] = str(pr['inss'].values[peri[2]])
            i['tipo_evento'] = 'periodico'


    for i in base_principal['publications']:
        conf = process.extractOne(str(i['veiculo']),
                                  cn['conferencia_limpo'],
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

  g = Graph()
  ontologia = g.parse("Publicacao.owl")#caminho
  pp  = Namespace("http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#")#iri
  g.bind("pp", pp )
  nome_autor = base_principal['name']
  Interesses_autor = base_principal['interests']
  Afiliação_autor = base_principal['affiliation']
  nome_autor_limpo = re.sub('[,|\s]+', '_', clear_char(nome_autor))
  Afiliacao_autor_limpo = re.sub('[,|\s]+', '_', clear_char(Afiliação_autor))

  #dados do autor 
  g.add((pp[nome_autor_limpo], RDF.type, pp.Autor_Cientifico))
  g.add((pp[nome_autor_limpo], pp.Nome_Autor, Literal(base_principal['name'])))
  g.add((pp[nome_autor_limpo], pp.Autor_Citacao, Literal(base_principal['citedby'])))
  g.add((pp[nome_autor_limpo], pp.Autor_IndiceH, Literal(base_principal['hindex'])))
  g.add((pp[nome_autor_limpo], pp.Autor_indiceI10, Literal(base_principal['i10index'])))


  g.add((pp[Afiliacao_autor_limpo], RDF.type, pp.Instituicao))
  g.add((pp[Afiliacao_autor_limpo], pp.Instituicao, Literal(Afiliação_autor)))

  g.add((pp[nome_autor_limpo], pp.Afiliado, pp[Afiliacao_autor_limpo]))

  #area de interesse
  for x in Interesses_autor:
      area = re.sub('[,|\s]+', '_', clear_char(x))

      g.add((pp[area], RDF.type, pp.Area_Pesquisa))
      g.add((pp[area], pp.Area_Pesquisa, Literal(x)))
      g.add((pp[nome_autor_limpo], pp.Pesquisa, pp[area]))

  #publicacao
  for x in range(len(base_principal['publications'])):

      titulo = base_principal['publications'][x]['title']
      titulo_clean = re.sub('[,|\s]+', '_', clear_char(titulo))
      veiculo = base_principal['publications'][x]['veiculo']
      veiculo_clean = re.sub('[,|\s]+', '_', clear_char(veiculo))
      autoria = nome_autor_limpo +'_Autoria_'+str(x)
      publicacao = nome_autor_limpo +'_Publicacao_'+str(x)

      #Cria Autoria 
      g.add((pp[autoria], RDF.type, pp.Autoria_Cientifica))
      g.add((pp[nome_autor_limpo], pp.Detem, pp[autoria]))
      
      #Cria Artigo
      g.add((pp[titulo_clean], RDF.type, pp.Texto_Autoral_Cientifico_Publicado))
      g.add((pp[titulo_clean], pp.Titulo_Artigo, Literal(titulo)))




      g.add((pp[autoria], pp.Refere_se, pp[titulo_clean]))
      #Cria Publicacao 
      g.add((pp[publicacao], RDF.type, pp.Publicacao))
      g.add((pp[titulo_clean], pp.Submetido, pp[publicacao]))
      g.add((pp[veiculo_clean], RDF.type, pp.Veiculo))
      g.add((pp[veiculo_clean], pp.Edicao_Ano, Literal(base_principal['publications'][x]['pub_year'])))
      g.add((pp[veiculo_clean], pp.Edicao_Nome, Literal(veiculo)))
      g.add((pp[publicacao], pp.Publicado_em , pp[veiculo_clean]))  


      if 'Qualis' in base_principal['publications'][x]:
          qualis = base_principal['publications'][x]['Qualis']
          #qualis_clear = re.sub('[,|\s]+', '_', clear_char(qualis))
          g.add((pp[veiculo_clean], pp.Classificada, pp[qualis]))
          g.add((pp[veiculo_clean], pp.Edicao_Tipo, Literal(base_principal['publications'][x]['tipo_evento'])))

  s = g.serialize(format='turtle')
  return s

def gera_tabela(g):

    dic={}
    p = []
    pp  = Namespace("http://www.semanticweb.org/fantasma/ontologies/2021/10/Publicacao#")#iri
    g.bind("pp", pp )
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

    for row in qres:
        d = {
        'evento': re.search("([^']*)",str(row.evento)).string,
        'Qualis': re.search("([^']*)",str(row.q)).string,
        'titulo' : re.search("([^']*)",str(row.titulo)).string,
        'tipo' : re.search("([^']*)",str(row.tipo)).string}
        p.append(d)
    for x in range(len(p)):
        if p[x]['tipo'] == 'periodico':
            if  p[x]['Qualis'] == 'A1':
                p[x][ 'Pontuacao'] = 1.000

            if p[x]['Qualis'] == 'A2':
                p[x][ 'Pontuacao'] =  0.875

            if p[x]['Qualis'] == 'A3':
                p[x][ 'Pontuacao'] = 0.750

            if p[x]['Qualis'] == 'A4':
                p[x][ 'Pontuacao'] =  0.625

            if p[x]['Qualis'] == 'B1':
                p[x][ 'Pontuacao'] =  0.500

            if p[x]['Qualis'] == 'B2':
                p[x][ 'Pontuacao'] = 0.200

            if p[x]['Qualis'] == 'B3':
                d[ 'Pontuacao'] =  0.100

            if p[x]['Qualis'] == 'B4':
                p[x][ 'Pontuacao'] =  0.050
        if p[x]['tipo'] == 'conferencia':
            if p[x]['Qualis'] == 'A1':
                p[x][ 'Pontuacao'] = 1.000
              
            if p[x]['Qualis'] == 'A2':
                p[x][ 'Pontuacao'] =  0.875

            if p[x]['Qualis'] == 'A3':
                p[x][ 'Pontuacao'] = 0.750

            if p[x]['Qualis'] == 'A4':
                p[x][ 'Pontuacao'] =  0.625

            if p[x]['Qualis'] == 'B1':
                p[x][ 'Pontuacao'] =  0.500

            if p[x]['Qualis'] == 'B2':
                p[x][ 'Pontuacao'] = 0.200

            if p[x]['Qualis'] == 'B3':
                p[x][ 'Pontuacao'] = 0.100

            if p[x]['Qualis'] == 'B4':
                p[x][ 'Pontuacao'] =  0.050

    data_qualis = pd.DataFrame(data=p)
    return data_qualis

def main():
    dados = []
    autor_name = []
    st.title('Ontologia de Publicação')
    selected = st.sidebar.text_input('')
    
    dados = busca(selected)
    for x in range(len(dados)):
        autor_name.append(dados[x]['name'])
    escolha = st.sidebar.selectbox('Autores', autor_name)
    if st.sidebar.button('Mostrar'):
        res = busca_index(escolha, dados)
        base = insere_dados(res, dados)
        onto = gera_ontologia(base)
        tabela = gera_tabela(onto)
        st.dataframe(tabela, 200, 100)

main()