import discord
from discord import app_commands
from discord.ext import commands, tasks
import database
import logging
import asyncio
from functools import partial
from datetime import datetime, timezone, time
import inspect
import math
import urllib.parse
import urllib.request
import json
import os
import pandas as pd

# Importar o python-jobspy
try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None

logger = logging.getLogger("project_emprego.monitor")

def fetch_jsearch_jobs(query: str, location: str, api_key: str) -> list:
    """Busca vagas de emprego usando a API JSearch (RapidAPI)."""
    import urllib.request
    import urllib.parse
    import json
    import logging

    logger = logging.getLogger("project_emprego.monitor.jsearch")
    url = "https://jsearch.p.rapidapi.com/search"
    
    # Parâmetros recomendados da API
    params = {
        "query": query,
        "page": "1",
        "num_pages": "1"
    }
    if location:
        params["location"] = location
    encoded_params = urllib.parse.urlencode(params)
    full_url = f"{url}?{encoded_params}"
    
    headers = {
        "X-RapidAPI-Key": api_key.strip(),
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjectEmpregoBot/1.0"
    }
    
    import ssl
    context = ssl._create_unverified_context()
    req = urllib.request.Request(full_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12, context=context) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                if res_data.get("status") == "OK":
                    raw_jobs = res_data.get("data", [])
                    mapped_jobs = []
                    for item in raw_jobs:
                        job_id = item.get("job_id")
                        if not job_id:
                            continue
                        
                        job_city = item.get("job_city") or ""
                        job_state = item.get("job_state") or ""
                        job_location = f"{job_city}, {job_state}".strip(", ")
                        
                        # Tentar converter lat/lon para float com segurança
                        lat = None
                        lon = None
                        try:
                            if item.get("job_latitude") is not None:
                                lat = float(item.get("job_latitude"))
                            if item.get("job_longitude") is not None:
                                lon = float(item.get("job_longitude"))
                        except (ValueError, TypeError):
                            pass

                        mapped_jobs.append({
                            "id": job_id,
                            "title": item.get("job_title") or "Vaga Sem Título",
                            "company": item.get("employer_name") or "Empresa Não Especificada",
                            "job_url": item.get("job_apply_link") or item.get("job_google_link") or "",
                            "location": job_location or item.get("job_country") or "Não especificada",
                            "city": job_city,
                            "state": job_state,
                            "site": "Google Jobs",
                            "latitude": lat,
                            "longitude": lon,
                            "description": item.get("job_description") or "Sem descrição disponível."
                        })
                    return mapped_jobs
                else:
                    logger.warning(f"JSearch API respondeu com status não OK: {res_data.get('status')}")
                    raise RuntimeError(f"JSearch respondeu com status {res_data.get('status')}")
            else:
                logger.warning(f"Erro HTTP {response.status} na API JSearch.")
                raise RuntimeError(f"Erro HTTP {response.status}")
    except Exception as e:
        logger.warning(f"Exceção ao chamar a API JSearch: {e}")
        raise e


def fetch_serpapi_jobs(query: str, location: str, api_key: str) -> list:
    """Busca vagas de emprego usando a API SerpApi (Google Jobs)."""
    import urllib.request
    import urllib.parse
    import json
    import logging

    logger = logging.getLogger("project_emprego.monitor.serpapi")
    url = "https://serpapi.com/search.json"
    
    params = {
        "engine": "google_jobs",
        "q": query,
        "api_key": api_key.strip(),
        "hl": "pt",
        "gl": "pt"
    }
    if location:
        params["location"] = location
    encoded_params = urllib.parse.urlencode(params)
    full_url = f"{url}?{encoded_params}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjectEmpregoBot/1.0"
    }
    
    import ssl
    context = ssl._create_unverified_context()
    req = urllib.request.Request(full_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12, context=context) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                raw_jobs = res_data.get("jobs_results", [])
                mapped_jobs = []
                for item in raw_jobs:
                    # O ID pode vir como um hash ou string, se ausente criamos a partir do link/titulo
                    job_id = item.get("job_id")
                    
                    apply_options = item.get("apply_options", [])
                    job_url = ""
                    if apply_options and isinstance(apply_options, list):
                        job_url = apply_options[0].get("link") or ""
                        
                    if not job_id:
                        job_id = job_url or item.get("title")
                    if not job_id:
                        continue
                        
                    mapped_jobs.append({
                        "id": job_id,
                        "title": item.get("title") or "Vaga Sem Título",
                        "company": item.get("company_name") or "Empresa Não Especificada",
                        "job_url": job_url,
                        "location": item.get("location") or "Não especificada",
                        "city": "",
                        "state": "",
                        "site": "Google Jobs",
                        "latitude": None,
                        "longitude": None,
                        "description": item.get("description") or "Sem descrição disponível."
                    })
                return mapped_jobs
            else:
                logger.warning(f"Erro HTTP {response.status} na API SerpApi.")
                raise RuntimeError(f"Erro HTTP {response.status}")
    except Exception as e:
        logger.warning(f"Exceção ao chamar a API SerpApi: {e}")
        raise e

def fetch_searchapi_jobs(query: str, location: str, api_key: str) -> list:
    """Busca vagas de emprego usando a API SearchApi.io (Google Jobs)."""
    import urllib.request
    import urllib.parse
    import json
    import logging

    logger = logging.getLogger("project_emprego.monitor.searchapi")
    url = "https://www.searchapi.io/api/v1/search"
    
    params = {
        "engine": "google_jobs",
        "q": query,
        "api_key": api_key.strip(),
        "hl": "pt",
        "gl": "pt"
    }
    if location:
        params["location"] = location
    encoded_params = urllib.parse.urlencode(params)
    full_url = f"{url}?{encoded_params}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjectEmpregoBot/1.0"
    }
    
    import ssl
    context = ssl._create_unverified_context()
    req = urllib.request.Request(full_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12, context=context) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                # O SearchApi coloca o resultado em 'jobs' ou 'jobs_results'
                raw_jobs = res_data.get("jobs", res_data.get("jobs_results", []))
                mapped_jobs = []
                for item in raw_jobs:
                    job_id = item.get("job_id")
                    
                    apply_options = item.get("apply_options", [])
                    job_url = ""
                    if apply_options and isinstance(apply_options, list):
                        job_url = apply_options[0].get("link") or ""
                        
                    if not job_id:
                        job_id = job_url or item.get("title")
                    if not job_id:
                        continue
                        
                    mapped_jobs.append({
                        "id": job_id,
                        "title": item.get("title") or "Vaga Sem Título",
                        "company": item.get("company_name") or "Empresa Não Especificada",
                        "job_url": job_url,
                        "location": item.get("location") or "Não especificada",
                        "city": "",
                        "state": "",
                        "site": "Google Jobs",
                        "latitude": None,
                        "longitude": None,
                        "description": item.get("description") or "Sem descrição disponível."
                    })
                return mapped_jobs
            else:
                logger.warning(f"Erro HTTP {response.status} na API SearchApi.")
                raise RuntimeError(f"Erro HTTP {response.status}")
    except Exception as e:
        logger.warning(f"Exceção ao chamar a API SearchApi: {e}")
        raise e

# Configuração Padrão do País para o Indeed/Glassdoor.
# Altere para 'brazil', 'usa', etc., dependendo do país de busca padrão.
DEFAULT_COUNTRY = "portugal"

# Termo de busca padrão para vagas de emprego.
# Sendo um bot geral, um termo amplo funciona bem.
DEFAULT_SEARCH_TERM = "vagas OR emprego"

class MonitorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.location_cache = {}  # Cache de geocodificação para evitar chamadas de API repetidas
        # Iniciar o loop de tarefas quando a cog é carregada
        self.monitor_loop.start()
        self.daily_summary_loop.start()

    def cog_unload(self):
        # Cancelar o loop de tarefas quando a cog é descarregada
        self.monitor_loop.cancel()
        self.daily_summary_loop.cancel()

    async def get_coordinates(self, location_name: str) -> tuple[float, float] | None:
        """Busca as coordenadas (lat, lon) de uma localização usando a API gratuita Nominatim.
        Utiliza um Lock global do bot para garantir o limite de no máximo 1 requisição por segundo.
        """
        if not location_name:
            return None
            
        location_cleaned = location_name.strip().lower()
        if location_cleaned in self.location_cache:
            return self.location_cache[location_cleaned]
            
        # Nominatim exige um User-Agent personalizado e identificável
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjectEmpregoBot/1.0 (contact: andyydias@outlook.com)"}
        
        encoded_location = urllib.parse.quote(location_name.strip())
        url = f"https://nominatim.openstreetmap.org/search?q={encoded_location}&format=json&limit=1"
        
        try:
            # Controlar a taxa de requisições globalmente usando o Lock do bot
            async with self.bot.nominatim_lock:
                now = asyncio.get_running_loop().time()
                elapsed = now - self.bot.last_nominatim_request_time
                # Se passou menos de 1.2 segundos desde a última requisição, esperamos a diferença
                if elapsed < 1.2:
                    await asyncio.sleep(1.2 - elapsed)
                
                # Executa a requisição HTTP síncrona em uma thread do executor
                def req():
                    import ssl
                    context = ssl._create_unverified_context()
                    request = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(request, timeout=6, context=context) as response:
                        data = json.loads(response.read().decode())
                        if data:
                            return float(data[0]["lat"]), float(data[0]["lon"])
                    return None
                    
                loop = asyncio.get_running_loop()
                coords = await loop.run_in_executor(None, req)
                
                # Atualizar o timestamp global após a execução do pedido
                self.bot.last_nominatim_request_time = asyncio.get_running_loop().time()
            
            if coords:
                self.location_cache[location_cleaned] = coords
                logger.info(f"Geocodificação de '{location_name}': {coords}")
                return coords
        except Exception as e:
            logger.error(f"Erro ao geocodificar '{location_name}': {e}")
            
        return None

    def get_haversine_distance(self, coords1: tuple[float, float], coords2: tuple[float, float]) -> float:
        """Calcula a distância em quilômetros entre duas coordenadas usando a fórmula de Haversine."""
        lat1, lon1 = coords1
        lat2, lon2 = coords2
        
        R = 6371.0  # Raio médio da Terra em km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    async def run_scraping_for_guild(self, guild_cfg: dict, channel: discord.TextChannel, is_forced: bool = False) -> int:
        """Executa a rotina de scraping e envia vagas novas para o canal configurado.
        Retorna o número de novas vagas enviadas.
        """
        if scrape_jobs is None:
            logger.error("A biblioteca python-jobspy não está instalada ou não pôde ser importada.")
            return 0

        guild_id = guild_cfg["guild_id"]
        cities_str = guild_cfg["cities"]
        engines_str = guild_cfg["search_engines"]

        cities = [c.strip() for c in cities_str.split(",") if c.strip()]
        engines = [e.strip() for e in engines_str.split(",") if e.strip()]

        if is_forced and "google" not in engines:
            engines.append("google")

        if not cities or not engines:
            logger.info(f"Configuração incompleta para o servidor {guild_id}.")
            return 0

        total_new_jobs = 0
        
        # Dicionário de estatísticas de varredura
        sweep_stats = {
            "cities": {},
            "google_api_used": {}
        }

        # Executar a busca de vagas para cada cidade cadastrada
        for city in cities:
            logger.info(f"Buscando vagas em '{city}' para o servidor {guild_id}...")
            
            # Buscar coordenadas da cidade de referência
            city_coords = await self.get_coordinates(city)
            if not city_coords:
                logger.warning(f"Não foi possível obter as coordenadas de '{city}'. A busca nessa cidade ignorará o filtro de 15km.")

            # Buscar individualmente por cada motor de busca para isolar erros
            for engine in engines:
                if city not in sweep_stats["cities"]:
                    sweep_stats["cities"][city] = {}
                sweep_stats["cities"][city][engine] = {
                    "found": 0,
                    "sent": 0,
                    "discarded_distance": 0,
                    "discarded_coords": 0,
                    "discarded_duplicate": 0,
                    "discarded_no_url": 0
                }

                # Se for o Google Jobs e não for uma varredura manual forçada, aplicar o rate limit de 6 horas
                if engine == "google" and not is_forced:
                    import time
                    last_run = await database.get_engine_last_run(guild_id, city, engine)
                    now = time.time()
                    elapsed = now - last_run
                    # 6 horas = 21600 segundos
                    if elapsed < 21600:
                        remaining_mins = int((21600 - elapsed) / 60)
                        logger.info(f"Pesquisa no Google Jobs para '{city}' ignorada. Próxima busca em {remaining_mins} minutos (limite de 6 horas).")
                        sweep_stats["google_api_used"][city] = f"Ignorado (Aguarde {remaining_mins}m)"
                        continue

                logger.info(f"Iniciando busca no '{engine}' para a cidade '{city}'...")
                
                try:
                    df = None
                    if engine == "google":
                        # Usar a API alternativa (JSearch, SerpApi ou SearchApi) se houver chave configurada no env
                        rapidapi_key = os.getenv("RAPIDAPI_KEY") or os.getenv("JSEARCH_API_KEY")
                        serpapi_key = os.getenv("SERPAPI_API_KEY")
                        searchapi_key = os.getenv("SEARCHAPI_API_KEY")
                        
                        # Se colocaram a chave do SearchApi (inicia com ak_) no RAPIDAPI_KEY por engano, redirecionamos
                        if rapidapi_key and rapidapi_key.strip().startswith("ak_"):
                            searchapi_key = rapidapi_key
                            rapidapi_key = None

                        # Criar uma lista ordenada das tentativas a fazer
                        attempts = []
                        if searchapi_key:
                            attempts.append(("SearchApi", searchapi_key))
                        if rapidapi_key:
                            attempts.append(("JSearch", rapidapi_key))
                        if serpapi_key:
                            attempts.append(("SerpApi", serpapi_key))

                        search_terms = ["vagas", "emprego"]
                        all_google_jobs = []
                        success = False
                        
                        # Formata a localização canônica (ex: "Covilhã, Portugal")
                        search_location = f"{city}, {DEFAULT_COUNTRY.capitalize()}"
                        
                        for term in search_terms:
                            term_jobs = []
                            term_success = False
                            
                            for provider, key in attempts:
                                try:
                                    if provider == "SearchApi":
                                        logger.info(f"Tentando buscar Google Jobs via SearchApi na cidade '{city}' para o termo '{term}'...")
                                        loop = asyncio.get_running_loop()
                                        term_jobs = await loop.run_in_executor(
                                            None,
                                            partial(fetch_searchapi_jobs, term, search_location, key)
                                        )
                                        term_success = True
                                    elif provider == "JSearch":
                                        logger.info(f"Tentando buscar Google Jobs via JSearch na cidade '{city}' para o termo '{term}'...")
                                        loop = asyncio.get_running_loop()
                                        term_jobs = await loop.run_in_executor(
                                            None,
                                            partial(fetch_jsearch_jobs, term, search_location, key)
                                        )
                                        term_success = True
                                    elif provider == "SerpApi":
                                        logger.info(f"Tentando buscar Google Jobs via SerpApi na cidade '{city}' para o termo '{term}'...")
                                        loop = asyncio.get_running_loop()
                                        term_jobs = await loop.run_in_executor(
                                            None,
                                            partial(fetch_serpapi_jobs, term, search_location, key)
                                        )
                                        term_success = True
                                        
                                    if term_success:
                                        logger.info(f"Busca via {provider} para o termo '{term}' concluída com sucesso. Encontradas {len(term_jobs)} vagas.")
                                        all_google_jobs.extend(term_jobs)
                                        success = True
                                        sweep_stats["google_api_used"][city] = provider
                                        await database.increment_api_usage(provider)
                                        break
                                except Exception as api_err:
                                    logger.warning(f"Chamada para o provedor {provider} com o termo '{term}' falhou: {api_err}. Tentando fallback...")
                                    term_success = False
                                    continue
                                    
                        if success:
                            # Remover duplicados de all_google_jobs baseando-se no 'id' de cada vaga
                            unique_google_jobs = []
                            seen_ids = set()
                            for job in all_google_jobs:
                                job_id = job.get("id")
                                if job_id not in seen_ids:
                                    seen_ids.add(job_id)
                                    unique_google_jobs.append(job)
                            
                            df = pd.DataFrame(unique_google_jobs) if unique_google_jobs else pd.DataFrame(columns=["id", "title", "company", "job_url", "location", "city", "state", "site", "latitude", "longitude"])
                        else:
                            logger.warning(
                                f"Nenhuma das APIs configuradas funcionou para Google Jobs (ou chaves ausentes). "
                                "Tentando usar a raspagem local do JobSpy como fallback..."
                            )
                            sweep_stats["google_api_used"][city] = "Scraping Local (JobSpy)"
                    
                    if df is None:
                        # Motor padrão do JobSpy (LinkedIn, Indeed, Glassdoor, ZipRecruiter, ou Fallback do Google)
                        sig = inspect.signature(scrape_jobs)
                        scrape_dfs = []
                        search_terms = ["vagas", "emprego"]
                        
                        for term in search_terms:
                            scrape_kwargs = {
                                "site_name": [engine],  # Raspagem isolada deste motor específico
                                "search_term": term,
                                "location": city,
                                "results_wanted": 50
                            }
                            
                            # Para o Google Jobs, usar google_search_term melhora drasticamente os resultados locais
                            if engine == "google" and "google_search_term" in sig.parameters:
                                scrape_kwargs["google_search_term"] = f"{term} em {city}"
                            
                            # country_indeed é importante para o Indeed local, adicionamos se suportado
                            if "country_indeed" in sig.parameters:
                                scrape_kwargs["country_indeed"] = DEFAULT_COUNTRY

                            # Executar o scraping em um executor para não bloquear a thread principal
                            loop = asyncio.get_running_loop()
                            
                            try:
                                # Chama a função síncrona do JobSpy passando as kwargs dinâmicas
                                term_df = await loop.run_in_executor(
                                    None,
                                    partial(scrape_jobs, **scrape_kwargs)
                                )
                                if term_df is not None and not term_df.empty:
                                    scrape_dfs.append(term_df)
                            except Exception as e:
                                # Se ocorrer qualquer erro de argumento inesperado, removemos os parâmetros extras e tentamos novamente de forma limpa
                                if "unexpected keyword argument" in str(e):
                                    logger.warning(f"Erro de parâmetro no JobSpy ({e}) para {engine}. Tentando executar a busca básica sem filtros...")
                                    for key in ["country_indeed", "hours_old", "google_search_term"]:
                                        scrape_kwargs.pop(key, None)
                                        
                                    term_df = await loop.run_in_executor(
                                        None,
                                        partial(scrape_jobs, **scrape_kwargs)
                                    )
                                    if term_df is not None and not term_df.empty:
                                        scrape_dfs.append(term_df)
                                else:
                                    raise e
                                    
                        if scrape_dfs:
                            df = pd.concat(scrape_dfs, ignore_index=True)
                            # Remover duplicados de forma segura
                            id_col = "id" if "id" in df.columns else ("job_url" if "job_url" in df.columns else None)
                            if id_col:
                                df = df.drop_duplicates(subset=[id_col])
                        else:
                            df = pd.DataFrame()
                    
                    # Se foi executada uma busca no Google Jobs, atualiza o timestamp de última execução
                    if engine == "google" and df is not None:
                        import time
                        await database.update_engine_last_run(guild_id, city, engine, time.time())

                    if df is not None:
                        sweep_stats["cities"][city][engine]["found"] = len(df)

                    if df is None or df.empty:
                        logger.info(f"Nenhuma vaga encontrada para '{city}' no site '{engine}' (servidor {guild_id}).")
                        continue

                    # Obter vagas que já foram enviadas anteriormente
                    sent_ids = await database.get_sent_job_ids(guild_id)
                    new_jobs_sent = []

                    # Iterar sobre as vagas encontradas
                    for idx, row in df.iterrows():
                        # Limpar e obter campos de forma segura contra variações de chaves (case/nome)
                        job_id = str(row.get("id") or row.get("job_url") or "")
                        if not job_id:
                            continue

                        # Evitar duplicados
                        if job_id in sent_ids:
                            sweep_stats["cities"][city][engine]["discarded_duplicate"] += 1
                            continue

                        # Extrair campos
                        title = str(row.get("title") or "Vaga Sem Título")
                        company = str(row.get("company") or "Empresa Não Especificada")
                        job_url = str(row.get("job_url") or "")
                        site_source = str(row.get("site") or engine).capitalize()
                        
                        row_city = str(row.get("city") or "")
                        row_state = str(row.get("state") or "")
                        if row_city or row_state:
                            job_location = f"{row_city}, {row_state}".strip(", ")
                        else:
                            job_location = str(row.get("location") or "")

                        # Se não houver URL, não enviamos pois o usuário precisa do link para se candidatar
                        if not job_url:
                            sweep_stats["cities"][city][engine]["discarded_no_url"] += 1
                            continue

                        # ---- Filtro de Distância de 15km ----
                        if city_coords and job_location:
                            # Otimização: se o nome da cidade configurada estiver contido no nome da cidade da vaga,
                            # assumimos distância 0km para economizar chamadas à API da Nominatim
                            if city.lower() in job_location.lower():
                                distance = 0.0
                            else:
                                # Tentar usar coordenadas fornecidas diretamente pela API (ex: JSearch)
                                job_coords = None
                                try:
                                    lat = row.get("latitude")
                                    lon = row.get("longitude")
                                    if lat is not None and not pd.isna(lat) and lon is not None and not pd.isna(lon):
                                        job_coords = (float(lat), float(lon))
                                        logger.info(f"Usando coordenadas fornecidas pela API para '{job_location}': {job_coords}")
                                except Exception:
                                    pass
                                    
                                if not job_coords:
                                    # Buscar coordenadas da vaga para comparar
                                    job_coords = await self.get_coordinates(job_location)
                                
                                if job_coords:
                                    distance = self.get_haversine_distance(city_coords, job_coords)
                                    logger.info(f"Distância calculada entre '{city}' e '{job_location}': {distance:.2f} km")
                                else:
                                    # Se não conseguir obter coordenadas da vaga, descartamos por segurança
                                    logger.warning(f"Não foi possível obter coordenadas para a vaga em '{job_location}'. Descartando vaga por segurança (raio de 15km).")
                                    sweep_stats["cities"][city][engine]["discarded_coords"] += 1
                                    continue
                            
                            # Descartar vagas que estejam fora do raio de 15km
                            if distance > 15.0:
                                logger.info(f"Vaga em '{job_location}' descartada. Distância: {distance:.2f} km (> 15 km).")
                                sweep_stats["cities"][city][engine]["discarded_distance"] += 1
                                continue

                        # Criar Embed de Vaga
                        embed = discord.Embed(
                            title=f"💼 {title[:250]}",
                            url=job_url,
                            color=0x2ec7a2,  # Cor moderna esmeralda
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.add_field(name="🏢 Empresa", value=company, inline=True)
                        embed.add_field(name="📍 Localização", value=job_location or "Não especificada", inline=True)
                        embed.add_field(name="🌐 Fonte", value=site_source, inline=True)
                        embed.set_footer(text="Project-Emprego • Nova Oportunidade")

                        # Enviar ao canal do Discord
                        try:
                            await channel.send(embed=embed)
                            new_jobs_sent.append(job_id)
                            sweep_stats["cities"][city][engine]["sent"] += 1
                            # Salvar os detalhes da vaga no BD para o painel web
                            description = str(row.get("description") or "Sem descrição disponível.")
                            await database.save_job(guild_id, job_id, title, company, job_url, job_location or "Não especificada", site_source, description)
                            # Adiciona um pequeno delay para não sofrer rate limit do discord
                            await asyncio.sleep(1)
                        except Exception as send_err:
                            logger.error(f"Erro ao enviar vaga {job_id}: {send_err}")

                    # Atualizar a lista de vagas enviadas no BD de uma só vez para esta cidade e motor
                    if new_jobs_sent:
                        await database.add_sent_jobs(guild_id, new_jobs_sent)
                        total_new_jobs += len(new_jobs_sent)
                        logger.info(f"Enviadas {len(new_jobs_sent)} novas vagas para o servidor {guild_id} via '{engine}' em '{city}'.")

                except Exception as engine_err:
                    # Tratar erros específicos de um site/motor sem interromper os restantes
                    logger.error(f"Erro durante scraping de '{city}' no site '{engine}' (servidor {guild_id}): {engine_err}")
                    continue

        # Criar Embed de Resumo da Varredura
        embed_title = "📊 Relatório de Varredura Automatizada" if not is_forced else "📊 Relatório de Varredura Forçada"
        summary_embed = discord.Embed(
            title=embed_title,
            color=0x3498db,  # Azul moderno e elegante
            timestamp=datetime.now(timezone.utc)
        )
        
        # Resumo Geral
        summary_embed.description = f"Varredura concluída para as cidades configuradas no servidor.\n**Total de novas vagas enviadas:** `{total_new_jobs}`"
        
        # Adicionar detalhes por cidade
        for city, engines_data in sweep_stats["cities"].items():
            city_details = []
            for engine, data in engines_data.items():
                engine_name = engine.capitalize()
                
                # Se for o motor do Google Jobs, adicionar qual API foi usada
                if engine == "google":
                    api_used = sweep_stats["google_api_used"].get(city, "Nenhum/Ignorado")
                    engine_name = f"Google Jobs ({api_used})"
                
                detail_str = (
                    f"**{engine_name}**:\n"
                    f"• Encontradas: `{data['found']}`\n"
                    f"• Enviadas: `{data['sent']}`\n"
                    f"• Descartadas (Duplicadas): `{data['discarded_duplicate']}`\n"
                    f"• Descartadas (Sem URL): `{data['discarded_no_url']}`\n"
                    f"• Descartadas (Raio > 15km): `{data['discarded_distance']}`\n"
                    f"• Descartadas (Sem coordenadas): `{data['discarded_coords']}`"
                )
                city_details.append(detail_str)
            
            if city_details:
                summary_embed.add_field(
                    name=f"📍 Cidade: {city}",
                    value="\n\n".join(city_details),
                    inline=False
                )
        
        # Buscar contagens acumuladas de uso de APIs do Google Jobs
        serpapi_calls = await database.get_api_usage("SerpApi")
        jsearch_calls = await database.get_api_usage("JSearch")
        searchapi_calls = await database.get_api_usage("SearchApi")
        
        summary_embed.add_field(
            name="📈 Uso Acumulado de APIs do Google Jobs",
            value=(
                f"• **SerpApi**: `{serpapi_calls}` chamadas\n"
                f"• **JSearch**: `{jsearch_calls}` chamadas\n"
                f"• **SearchApi**: `{searchapi_calls}` chamadas"
            ),
            inline=False
        )
        
        summary_embed.set_footer(text="Project-Emprego • Sistema de Monitoramento")
        
        # Enviar o embed de resumo para o canal
        try:
            await channel.send(embed=summary_embed)
        except Exception as send_summary_err:
            logger.error(f"Erro ao enviar embed de resumo: {send_summary_err}")

        return total_new_jobs

    @tasks.loop(minutes=10)
    async def monitor_loop(self):
        """Loop executado a cada 10 minutos para verificar novas vagas nos servidores ativos."""
        logger.info("Iniciando ciclo de verificação de vagas...")

        try:
            # Buscar todos os servidores ativos (status = 'ON')
            active_guilds = await database.get_active_guild_configs()
            if not active_guilds:
                logger.info("Nenhum servidor com monitoramento ativo ('ON').")
                return

            for guild_cfg in active_guilds:
                guild_id = guild_cfg["guild_id"]
                channel_id = guild_cfg["channel_id"]

                # Obter o canal do Discord
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception as e:
                        logger.warning(f"Não foi possível obter o canal {channel_id} para o servidor {guild_id}: {e}")
                        continue

                # Chamar o utilitário de raspagem
                await self.run_scraping_for_guild(guild_cfg, channel)

        except Exception as loop_err:
            logger.error(f"Erro crítico no loop de monitoramento: {loop_err}")

    @monitor_loop.before_loop
    async def before_monitor_loop(self):
        # Aguardar o bot estar completamente pronto antes de rodar o loop
        await self.bot.wait_until_ready()
        logger.info("Bot pronto. Sincronização e loop de monitoramento iniciados.")

    @app_commands.command(name="varrer", description="Força uma varredura imediata de novas vagas de emprego para este servidor.")
    @app_commands.default_permissions(administrator=True)
    async def force_sweep(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        # Verificar se o servidor já está cadastrado
        config = await database.get_guild_config(guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Este servidor ainda não foi configurado. Por favor, execute o comando `/setup` primeiro.",
                ephemeral=True
            )
            return

        # Deferir a resposta do bot já que a raspagem demora mais de 3 segundos
        await interaction.response.defer(ephemeral=True)

        channel_id = config["channel_id"]
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Não foi possível obter o canal de alertas configurado (ID: {channel_id}). Erro: {e}",
                    ephemeral=True
                )
                return

        # Notificar o utilizador sobre o início
        await interaction.followup.send(
            "🔍 **A iniciar varredura imediata de vagas...** Isto pode demorar alguns segundos. Por favor, aguarde.",
            ephemeral=True
        )

        try:
            total_jobs = await self.run_scraping_for_guild(config, channel, is_forced=True)
            
            if total_jobs > 0:
                await interaction.followup.send(
                    f"✅ **Varredura forçada concluída!** Encontradas e enviadas **{total_jobs}** novas vagas para o canal {channel.mention}.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "ℹ️ **Varredura forçada concluída!** Não foram encontradas novas vagas nesta busca.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Erro na varredura forçada para servidor {guild_id}: {e}")
            await interaction.followup.send(
                f"❌ Ocorreu um erro inesperado durante a varredura: `{e}`",
                ephemeral=True
            )

    @app_commands.command(name="start", description="Inicia/Retoma o envio automático de vagas neste servidor.")
    @app_commands.default_permissions(administrator=True)
    async def start_monitor(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        # Verificar se o servidor já está cadastrado
        config = await database.get_guild_config(guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Este servidor ainda não foi configurado. Por favor, execute o comando `/setup` primeiro.",
                ephemeral=True
            )
            return

        if config["status"] == "ON":
            await interaction.response.send_message(
                "ℹ️ O monitoramento automático de vagas já está **ativo** (`ON`) neste servidor.",
                ephemeral=True
            )
            return

        try:
            # Atualizar status no BD
            await database.set_guild_status(guild_id, "ON")
            await interaction.response.send_message(
                "✅ O monitoramento automático de vagas foi **iniciado** para este servidor!",
                ephemeral=False
            )
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao iniciar: {e}", ephemeral=True)

    @app_commands.command(name="stop", description="Pausa o envio automático de vagas neste servidor.")
    @app_commands.default_permissions(administrator=True)
    async def stop_monitor(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        # Verificar se o servidor já está cadastrado
        config = await database.get_guild_config(guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Este servidor ainda não foi configurado. Por favor, execute o comando `/setup` primeiro.",
                ephemeral=True
            )
            return

        if config["status"] == "OFF":
            await interaction.response.send_message(
                "ℹ️ O monitoramento automático de vagas já está **pausado** (`OFF`) neste servidor.",
                ephemeral=True
            )
            return

        try:
            # Atualizar status no BD
            await database.set_guild_status(guild_id, "OFF")
            await interaction.response.send_message(
                "🛑 O monitoramento automático de vagas foi **pausado** para este servidor!",
                ephemeral=False
            )
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao pausar: {e}", ephemeral=True)

    @tasks.loop(time=time(hour=0, minute=0))
    async def daily_summary_loop(self):
        """Loop diário executado às 00:00 para enviar o resumo das últimas 24 horas."""
        logger.info("Iniciando ciclo do resumo diário...")
        try:
            # Buscar todos os servidores ativos (status = 'ON')
            active_guilds = await database.get_active_guild_configs()
            if not active_guilds:
                return

            for guild_cfg in active_guilds:
                guild_id = guild_cfg["guild_id"]
                daily_channel_id = guild_cfg.get("daily_channel_id")
                
                # Se não houver canal de resumo diário configurado para este servidor, ignora
                if not daily_channel_id:
                    continue

                # Obter o canal do Discord
                channel = self.bot.get_channel(daily_channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(daily_channel_id)
                    except Exception as e:
                        logger.warning(f"Não foi possível obter o canal diário {daily_channel_id} para o servidor {guild_id}: {e}")
                        continue

                # Gerar estatísticas das últimas 24 horas (desde ontem às 00:00)
                # 24 horas em segundos = 24 * 60 * 60 = 86400
                import time as pytime
                since_timestamp = pytime.time() - 86400

                # 1. Quantidade de vagas encontradas
                found_count = 0
                async with database.aiosqlite.connect(database.DB_FILE) as db:
                    async with db.execute("SELECT COUNT(*) FROM jobs WHERE guild_id = ? AND timestamp >= ?", (guild_id, since_timestamp)) as cursor:
                        row = await cursor.fetchone()
                        found_count = row[0] if row else 0

                # 2. Vagas submetidas (aguardando ou respondidas) nas últimas 24 horas
                submitted_count = 0
                async with database.aiosqlite.connect(database.DB_FILE) as db:
                    async with db.execute("""
                        SELECT COUNT(*) FROM user_job_status ujs
                        JOIN jobs j ON ujs.job_id = j.id
                        WHERE j.guild_id = ? AND ujs.status IN ('submetida', 'positiva', 'negativa') AND ujs.timestamp >= ?
                    """, (guild_id, since_timestamp)) as cursor:
                        row = await cursor.fetchone()
                        submitted_count = row[0] if row else 0

                # 3. Vagas descartadas nas últimas 24 horas
                discarded_count = 0
                async with database.aiosqlite.connect(database.DB_FILE) as db:
                    async with db.execute("""
                        SELECT COUNT(*) FROM user_job_status ujs
                        JOIN jobs j ON ujs.job_id = j.id
                        WHERE j.guild_id = ? AND ujs.status = 'descartada' AND ujs.timestamp >= ?
                    """, (guild_id, since_timestamp)) as cursor:
                        row = await cursor.fetchone()
                        discarded_count = row[0] if row else 0

                # 4. Vagas de sucesso (resposta positiva) nas últimas 24 horas
                success_jobs = []
                async with database.aiosqlite.connect(database.DB_FILE) as db:
                    db.row_factory = database.aiosqlite.Row
                    async with db.execute("""
                        SELECT j.title, j.company FROM user_job_status ujs
                        JOIN jobs j ON ujs.job_id = j.id
                        WHERE j.guild_id = ? AND ujs.status = 'positiva' AND ujs.timestamp >= ?
                    """, (guild_id, since_timestamp)) as cursor:
                        rows = await cursor.fetchall()
                        success_jobs = [dict(r) for r in rows]

                # Construir embed de resumo diário
                embed = discord.Embed(
                    title="📅 Resumo Diário de Candidaturas",
                    description="Fluxo de vagas e progresso das candidaturas nas últimas 24 horas.",
                    color=0x3498db,
                    timestamp=datetime.now(timezone.utc)
                )
                
                embed.add_field(name="🔍 Vagas Encontradas", value=f"**{found_count}** novas vagas", inline=True)
                embed.add_field(name="📩 Candidaturas Submetidas", value=f"**{submitted_count}** enviadas", inline=True)
                embed.add_field(name="🗑️ Vagas Descartadas", value=f"**{discarded_count}** removidas", inline=True)

                if success_jobs:
                    success_text = "\n".join([f"• **{j['title']}** na empresa *{j['company']}*" for j in success_jobs])
                    embed.add_field(name="🎉 Sucessos do Dia!", value=success_text, inline=False)
                    embed.color = 0x2ecc71  # Mudar para verde se houver sucesso
                else:
                    embed.add_field(name="🎉 Sucessos do Dia!", value="Nenhuma resposta positiva recebida hoje. Continue a tentar! 💪", inline=False)

                embed.set_footer(text="Project-Emprego • Relatório Diário Automático")
                
                try:
                    await channel.send(embed=embed)
                except Exception as send_err:
                    logger.error(f"Erro ao enviar resumo diário para o canal {daily_channel_id}: {send_err}")

        except Exception as loop_err:
            logger.error(f"Erro crítico no loop do resumo diário: {loop_err}")

    @daily_summary_loop.before_loop
    async def before_daily_summary_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorCog(bot))
