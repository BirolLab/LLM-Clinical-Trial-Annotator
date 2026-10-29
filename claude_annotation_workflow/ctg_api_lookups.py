#!/usr/bin/env python3
"""
ampharvest - CSV of NCT ids in, one CSV of everything those trials touch out.

Only live, keyless, free APIs. No bulk downloads, no HTML scraping, no keys
required anywhere.

Sources
  clinicaltrials   ClinicalTrials.gov API v2
  openfda          api.fda.gov: label, ndc, event, drugsfda
  pubmed           NCBI E-utilities
  pmc              NCBI E-utilities + OA service
  pmc_bioc         PMC BioC full text (open-access subset)
  europepmc        Europe PMC search
  openalex         OpenAlex works
  crossref         Crossref works
  uniprot          UniProt REST
  ebi_proteins     EBI Proteins API (+ features)
  chembl           ChEMBL molecule / activity / drug_indication
  rcsb_pdb         RCSB search v2 + data REST
  pdbe             PDBe Solr + entry summary
  intact           IntAct findInteractions
  iuphar           IUPHAR/BPS Guide to Pharmacology
  dbaasp           DBAASP peptides (keyless v3/v4)

What each source is queried with
  NCT id      openfda, pubmed, pmc, pmc_bioc, europepmc, openalex, crossref
  drug name   uniprot, ebi_proteins, chembl, rcsb_pdb, pdbe, intact, iuphar,
              dbaasp   (names come from the trial's interventions + otherNames;
                        uniprot and dbaasp also take --sequence-col sequences)

Each source keeps at most --limit records per trial (default 5): the request
asks for that many and a hard budget drops anything past it, so a source that
loops over several drug names still contributes only its top 5.

Install:  pip install requests
Usage:    python ampharvest.py --selftest --email you@example.org
          python ampharvest.py -i ncts.csv -o out --email you@example.org
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
import traceback
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

import requests

__version__ = "2.0.0"

MAX_VAL = 8000  # max chars per CSV cell; longer text is split across fields
NCT_RE = re.compile(r"NCT\d{8}", re.I)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BIOC = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi"
CTG = "https://clinicaltrials.gov/api/v2/studies"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
GTOP = "https://www.guidetopharmacology.org/services"
DBAASP = "https://dbaasp.org"

# Minimum seconds between requests per host. Conservative on purpose: these are
# free public services and an IP ban costs more than waiting.
HOST_INTERVALS = {
    "eutils.ncbi.nlm.nih.gov": 0.40,   # 3/s keyless, 10/s with a free key
    "www.ncbi.nlm.nih.gov": 0.40,
    "api.fda.gov": 0.30,               # 240/min
    "clinicaltrials.gov": 0.25,
    "rest.uniprot.org": 0.20,
    "www.ebi.ac.uk": 0.25,
    "search.rcsb.org": 0.20,
    "data.rcsb.org": 0.20,
    "api.openalex.org": 0.20,
    "api.crossref.org": 0.25,
    "www.guidetopharmacology.org": 1.00,
    "dbaasp.org": 1.00,
    "_default": 1.00,
}


# ───────────────────────────────────────────────────────────── http + cache
NETWORK_FS = {"nfs", "nfs4", "cifs", "smbfs", "smb3", "afs", "lustre", "gpfs",
              "beegfs", "ceph", "glusterfs", "fuse.sshfs", "9p"}


def fs_type(path: str) -> str:
    """Filesystem type for a path, from /proc/mounts. '' if undeterminable
    (macOS, BSD). SQLite is only safe on a local filesystem."""
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as f:
            mounts = [(ln.split()[1], ln.split()[2]) for ln in f if len(ln.split()) > 2]
    except OSError:
        return ""
    path = os.path.abspath(path)
    best, kind = "", ""
    for mp, t in mounts:
        if (path == mp or path.startswith(mp.rstrip("/") + "/")) and len(mp) > len(best):
            best, kind = mp, t
    return kind


class Cache:
    """Every response lands on disk, so re-runs are free and hit no limits."""

    MAX_FAILS = 3

    def __init__(self, path: str, ttl_days: float = 30.0):
        self.path = os.path.abspath(path)
        self.ttl = ttl_days * 86400
        self._lock = threading.Lock()
        self.disabled = False
        self.fails = 0
        self.fs = fs_type(self.path)
        self.networked = self.fs in NETWORK_FS
        if self.networked:
            print(f"!! cache is on a {self.fs} filesystem: {self.path}\n"
                  f"!! SQLite needs POSIX locking and journal sidecar files, "
                  f"which network mounts do badly -- this is what causes\n"
                  f"!! 'unable to open database file' mid-run. Put it on local "
                  f"disk instead:  --cache /tmp/ampharvest-cache.sqlite\n",
                  file=sys.stderr)
        parent = os.path.dirname(self.path)
        if parent and not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError as e:
                raise SystemExit(
                    f"cannot create the cache directory {parent}: {e}\n"
                    f"Pick a path that exists, on local disk:  "
                    f"--cache /tmp/ampharvest-cache.sqlite")
        try:
            self.db = sqlite3.connect(self.path, check_same_thread=False,
                                      timeout=60)
        except sqlite3.OperationalError as e:
            raise SystemExit(
                f"cannot open the cache at {self.path}: {e}\n"
                f"'unable to open database file' here means the directory is "
                f"missing, unwritable, or\na network mount SQLite can't lock. "
                f"Use local disk:  --cache /tmp/ampharvest-cache.sqlite")
        if self.networked:
            # WAL is impossible over NFS (needs shared memory). Rollback journal
            # plus an exclusive lock held for the whole run: one lock operation
            # instead of two per query, which is what NFS chokes on.
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA locking_mode=EXCLUSIVE")
        else:
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=60000")
        self.db.execute("CREATE TABLE IF NOT EXISTS c "
                        "(k TEXT PRIMARY KEY, status INT, body BLOB, ts REAL, url TEXT)")
        self.db.commit()

    def _fail(self, e: Exception):
        """A dead cache must not kill the harvest: log once, carry on uncached.
        'unable to open database file' is usually a full disk, so the CSV
        writes are probably next."""
        self.fails += 1
        if self.fails >= self.MAX_FAILS and not self.disabled:
            self.disabled = True
            why = (f"the cache is on {self.fs}, a network filesystem - move it "
                   f"to local disk with --cache /tmp/ampharvest-cache.sqlite"
                   if self.networked
                   else "check free disk and quota (df -h, quota -s)")
            print(f"\n!! cache disabled after {self.fails} sqlite errors "
                  f"({e}).\n!! {self.path}\n!! Likely cause: {why}."
                  f"\n!! Continuing without cache: slower, and re-runs will "
                  f"refetch.\n", file=sys.stderr)

    @staticmethod
    def key(method: str, url: str, params: Any, data: Any) -> str:
        blob = json.dumps([method.upper(), url, params or {}, data or {}],
                          sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    def get(self, k: str):
        if self.disabled:
            return None
        try:
            with self._lock:
                row = self.db.execute("SELECT status, body, ts FROM c WHERE k=?",
                                      (k,)).fetchone()
        except sqlite3.Error as e:
            self._fail(e)
            return None
        if not row:
            return None
        status, body, ts = row
        if self.ttl and (time.time() - ts) > self.ttl:
            return None
        return status, body

    def put(self, k: str, status: int, body: bytes, url: str):
        if self.disabled:
            return
        try:
            with self._lock:
                self.db.execute("INSERT OR REPLACE INTO c VALUES (?,?,?,?,?)",
                                (k, status, body, time.time(), url))
                self.db.commit()
        except sqlite3.Error as e:
            self._fail(e)


@dataclass
class Client:
    cache: Cache
    email: str = "anonymous@example.org"
    timeout: float = 45.0
    retries: int = 3
    offline: bool = False
    _last: dict = field(default_factory=dict)
    _lock: Any = field(default_factory=threading.Lock)

    def __post_init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = (
            f"ampharvest/{__version__} (research; {self.email})")
        self.s.headers["Accept-Encoding"] = "gzip, deflate"

    def _throttle(self, url: str):
        host = urllib.parse.urlparse(url).netloc
        gap = HOST_INTERVALS.get(host, HOST_INTERVALS["_default"])
        with self._lock:
            wait = gap - (time.time() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.time()

    def request(self, url: str, method: str = "GET", params: dict | None = None,
                data: dict | None = None, headers: dict | None = None,
                use_cache: bool = True) -> tuple[int, bytes]:
        k = Cache.key(method, url, params, data)
        if use_cache:
            hit = self.cache.get(k)
            if hit:
                return hit
        if self.offline:
            return 0, b""

        last = None
        for attempt in range(self.retries):
            self._throttle(url)
            try:
                r = self.s.request(method, url, params=params, data=data,
                                   headers=headers, timeout=self.timeout)
            except requests.RequestException as e:
                last = e
                time.sleep(2 ** attempt + random.random())
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = RuntimeError(f"HTTP {r.status_code}")
                time.sleep(2 ** attempt * 2 + random.random())
                continue
            if use_cache and r.status_code < 400:
                self.cache.put(k, r.status_code, r.content, r.url)
            return r.status_code, r.content
        raise RuntimeError(f"{url}: {last}")

    def json(self, url: str, **kw) -> Any:
        _, body = self.request(url, **kw)
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def text(self, url: str, **kw) -> str:
        _, body = self.request(url, **kw)
        return body.decode("utf-8", errors="replace")


# ────────────────────────────────────────────────────────────── core types
@dataclass
class Record:
    source: str
    nct_id: str
    query: str
    record_id: str
    fields: dict[str, Any]


_NOISE = re.compile(
    r"\b(placebo|tablet|capsule|injection|infusion|solution|cream|ointment|gel|"
    r"vehicle|comparator|oral|topical|intravenous|subcutaneous|iv|im|sc|"
    r"dose|doses|dosage|arm|cohort|group|standard of care|usual care|matching|"
    r"saline|sham|no intervention|best supportive care)\b", re.I)
_DOSE = re.compile(
    r"\d+(\.\d+)?\s*(mg/kg|mg|mcg|µg|ug|kg|g|ml|l|%|iu|units?|w/w|v/v)(?![a-z])", re.I)
_PREFIX = re.compile(
    r"^(drug|biological|device|procedure|dietary supplement|radiation|behavioral|"
    r"genetic|combination product|diagnostic test|other)\s*:\s*", re.I)


def split_intervention(name: str) -> list[str]:
    """'Drug: LL-37 gel 0.5% (Ropocamptide)' -> ['LL-37', 'Ropocamptide'].
    Pure-noise arms ('Placebo', 'Standard of care') drop out entirely."""
    name = _PREFIX.sub("", name.strip())
    if not name:
        return []
    out = []
    for p in re.split(r"[/;,]| \+ | and | vs\.? |\(|\)", name):
        p = _DOSE.sub(" ", _NOISE.sub(" ", p))
        p = re.sub(r"\s+", " ", p).strip(" -.:%+")
        if len(p) >= 3 and not p.isdigit():
            out.append(p)
    if out:
        return out
    return [] if _NOISE.search(name) else [name]


@dataclass
class TrialContext:
    """Everything stage 1 learned about one NCT id; drives every other source."""
    nct_id: str
    title: str = ""
    conditions: list[str] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
    sponsors: list[str] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
    other_ids: list[str] = field(default_factory=list)
    sequences: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def terms(self) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for t in self.interventions:
            for cand in split_intervention(t):
                if cand.lower() not in seen:
                    seen.add(cand.lower())
                    out.append(cand)
        return out


class Budget:
    """Hard cap on records kept per source label, per trial. Sources check
    room() before making a request they don't need; the runner calls take() as
    records flow past, so the two stay in sync during generation."""

    def __init__(self, cap: int):
        self.cap = cap
        self.n: dict[str, int] = {}
        self._lock = threading.Lock()

    def room(self, label: str) -> bool:
        with self._lock:
            return self.n.get(label, 0) < self.cap

    def take(self, label: str) -> bool:
        with self._lock:
            c = self.n.get(label, 0)
            if c >= self.cap:
                return False
            self.n[label] = c + 1
            return True


@dataclass
class Env:
    http: Client
    email: str = "anonymous@example.org"
    ncbi_api_key: str | None = None
    openfda_api_key: str | None = None
    per_source_limit: int = 5
    full_text: bool = True
    budget: Any = None

    def room(self, label: str) -> bool:
        """False once this label has hit the cap; skip the call."""
        return self.budget is None or self.budget.room(label)


# the sources that actually carry an abstract
ABSTRACT_SOURCES = ["pubmed", "europepmc", "openalex", "crossref"]
# the molecular sources, queried by drug name
PROTEIN_SOURCES = ["uniprot", "ebi_proteins", "chembl", "rcsb_pdb", "pdbe",
                   "intact", "iuphar", "dbaasp"]
# shorthands usable in -s, e.g.  -s abstracts,proteins
SOURCE_GROUPS = {
    "abstracts": ABSTRACT_SOURCES,
    "literature": ABSTRACT_SOURCES + ["pmc", "pmc_bioc"],
    "proteins": PROTEIN_SOURCES,
    "molecular": PROTEIN_SOURCES,
    "trials": ["clinicaltrials", "openfda"],
}

SourceFn = Callable[[TrialContext, Env], Iterable[Record]]
REGISTRY: dict[str, SourceFn] = {}
PROBES: dict[str, Callable[[Env], str]] = {}


def source(name: str):
    def deco(fn: SourceFn) -> SourceFn:
        REGISTRY[name] = fn
        return fn
    return deco


def probe(name: str):
    def deco(fn):
        PROBES[name] = fn
        return fn
    return deco


def flatten(obj: Any, prefix: str = "", out: dict | None = None) -> dict[str, str]:
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, (list, tuple)):
        if obj and all(not isinstance(i, (dict, list, tuple)) for i in obj):
            out[prefix or "value"] = " | ".join(str(i) for i in obj)[:MAX_VAL]
        else:
            for i, v in enumerate(obj):
                flatten(v, f"{prefix}[{i}]", out)
    else:
        if obj not in (None, "", [], {}):
            out[prefix or "value"] = str(obj)[:MAX_VAL]
    return out


def chunk(text: str, size: int = MAX_VAL) -> Iterator[tuple[int, str]]:
    for i in range(0, len(text), size):
        yield i // size, text[i:i + size]


# ─────────────────────────────────────────── stage 1: ClinicalTrials.gov v2
def build_context(nct_id: str, env: Env, sequences: list[str] | None = None):
    ctx = TrialContext(nct_id=nct_id, sequences=sequences or [])
    data = env.http.json(f"{CTG}/{nct_id}", params={"format": "json"})
    if not data:
        return ctx
    ctx.raw = data
    p = data.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    ctx.title = ident.get("briefTitle") or ident.get("officialTitle") or ""
    ctx.other_ids = [s for s in (
        [ident.get("orgStudyIdInfo", {}).get("id", "")]
        + [x.get("id", "") for x in ident.get("secondaryIdInfos", [])]) if s]
    ctx.conditions = p.get("conditionsModule", {}).get("conditions", []) or []
    arms = p.get("armsInterventionsModule", {})
    for i in arms.get("interventions", []) or []:
        if i.get("name"):
            ctx.interventions.append(i["name"])
        # otherNames is where the real molecule name usually hides
        ctx.interventions.extend(i.get("otherNames", []) or [])
    spon = p.get("sponsorCollaboratorsModule", {})
    ctx.sponsors = [s for s in (
        [spon.get("leadSponsor", {}).get("name", "")]
        + [c.get("name", "") for c in spon.get("collaborators", []) or []]) if s]
    ctx.phases = p.get("designModule", {}).get("phases", []) or []
    return ctx


@source("clinicaltrials")
def s_clinicaltrials(ctx: TrialContext, env: Env) -> Iterable[Record]:
    if ctx.raw:
        yield Record("clinicaltrials", ctx.nct_id, ctx.nct_id, ctx.nct_id,
                     flatten(ctx.raw))


@probe("clinicaltrials")
def p_ctg(env: Env) -> str:
    d = env.http.json(f"{CTG}/NCT00000102", params={"format": "json"},
                      use_cache=False)
    return "ok" if d else "no data"


# ───────────────────────────────────────────────────────────────── openFDA
FDA_ENDPOINTS = {
    "label": "https://api.fda.gov/drug/label.json",
    "ndc": "https://api.fda.gov/drug/ndc.json",
    "event": "https://api.fda.gov/drug/event.json",
    "drugsfda": "https://api.fda.gov/drug/drugsfda.json",
}


@source("openfda")
def s_openfda(ctx: TrialContext, env: Env) -> Iterable[Record]:
    """Queried by NCT id. openFDA indexes no trial-id field, so this is a
    free-text match over the whole record: labels that cite the trial in their
    clinical studies section hit, most records won't."""
    for kind, url in FDA_ENDPOINTS.items():
        if not env.room("openfda"):
            return
        params = {"search": ctx.nct_id, "limit": min(env.per_source_limit, 100)}
        if env.openfda_api_key:
            params["api_key"] = env.openfda_api_key
        d = env.http.json(url, params=params)
        if not d or "error" in d:  # NOT_FOUND is the normal no-match reply
            continue
        for i, res in enumerate(d.get("results", [])):
            rid = (res.get("id") or res.get("product_ndc")
                   or res.get("safetyreportid") or res.get("application_number")
                   or f"{kind}{i:03d}")
            rec = flatten(res)
            rec["_endpoint"] = kind
            yield Record("openfda", ctx.nct_id, f"{kind}:{ctx.nct_id}",
                         str(rid), rec)


@probe("openfda")
def p_fda(env: Env) -> str:
    d = env.http.json(FDA_ENDPOINTS["label"],
                      params={"search": "NCT00000102", "limit": 1},
                      use_cache=False) or {}
    if d.get("results"):
        return "ok"
    return "ok (endpoint live, no NCT match)" if d else "no response"


# ──────────────────────────────────────────────────────── PubMed / PMC / BioC
def eparams(env: Env, **kw) -> dict:
    p = {"tool": "ampharvest", "email": env.email}
    if env.ncbi_api_key:
        p["api_key"] = env.ncbi_api_key
    p.update(kw)
    return p


def nct_query(ctx: TrialContext, db: str = "pubmed") -> str:
    """NCT id only. PubMed indexes it under Secondary Source ID for papers that
    registered it; the All Fields arm catches mentions in the abstract or
    databank list. PMC has no such field, so it gets a plain term match."""
    if db == "pubmed":
        return f"{ctx.nct_id}[Secondary Source ID] OR {ctx.nct_id}[All Fields]"
    return ctx.nct_id


def esearch(env: Env, db: str, term: str, retmax: int) -> list[str]:
    d = env.http.json(f"{EUTILS}/esearch.fcgi",
                      params=eparams(env, db=db, term=term, retmode="json",
                                     retmax=retmax))
    try:
        return d["esearchresult"]["idlist"]
    except (KeyError, TypeError):
        return []


def parse_pubmed_xml(xml: str) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for art in root.iter("PubmedArticle"):
        def txt(path, sep=" "):
            return sep.join(
                (e.text or "").strip() for e in art.findall(path) if e.text)
        rec = {
            "pmid": txt(".//PMID"),
            "doi": txt(".//ArticleId[@IdType='doi']"),
            "pmcid": txt(".//ArticleId[@IdType='pmc']"),
            "title": txt(".//ArticleTitle"),
            "journal": txt(".//Journal/Title"),
            "year": txt(".//PubDate/Year") or txt(".//PubDate/MedlineDate"),
            "abstract": txt(".//Abstract/AbstractText", sep="\n"),
            "authors": "; ".join(
                f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
                for a in art.findall(".//Author")),
            "pubtypes": txt(".//PublicationType", sep=" | "),
            "mesh": " | ".join(e.findtext("DescriptorName", "")
                               for e in art.findall(".//MeshHeading")),
            "databank_accessions": txt(".//AccessionNumber", sep=" | "),
        }
        out.append({k: v for k, v in rec.items() if v})
    return out


@source("pubmed")
def s_pubmed(ctx: TrialContext, env: Env) -> Iterable[Record]:
    q = nct_query(ctx, "pubmed")
    pmids = esearch(env, "pubmed", q, env.per_source_limit)
    if not pmids:
        return
    xml = env.http.text(f"{EUTILS}/efetch.fcgi", method="POST",
                        data=eparams(env, db="pubmed", id=",".join(pmids),
                                     retmode="xml"))
    for rec in parse_pubmed_xml(xml):
        yield Record("pubmed", ctx.nct_id, q, rec.get("pmid", "?"), rec)


@probe("pubmed")
def p_pubmed(env: Env) -> str:
    return "ok" if esearch(env, "pubmed", "antimicrobial peptide", 1) else "no ids"


def pmcids(ctx: TrialContext, env: Env) -> list[tuple[str, str]]:
    """(pmcid, query) for the NCT id: direct PMC search, plus elink from the
    PubMed hits to catch papers whose PMC record doesn't name the id."""
    pq = nct_query(ctx, "pmc")
    pairs = [(f"PMC{pid}", pq)
             for pid in esearch(env, "pmc", pq, env.per_source_limit)]
    pmids = esearch(env, "pubmed", nct_query(ctx, "pubmed"), env.per_source_limit)
    if pmids:
        d = env.http.json(f"{EUTILS}/elink.fcgi", method="POST",
                          data=eparams(env, dbfrom="pubmed", db="pmc",
                                       id=",".join(pmids), retmode="json")) or {}
        for ls in d.get("linksets", []):
            for db in ls.get("linksetdbs", []):
                for pid in db.get("links", []):
                    pairs.append((f"PMC{pid}", f"elink:{ctx.nct_id}"))
    uniq: dict[str, str] = {}
    for pmcid, q in pairs:
        uniq.setdefault(pmcid, q)
    return list(uniq.items())[: env.per_source_limit]


@source("pmc")
def s_pmc(ctx: TrialContext, env: Env) -> Iterable[Record]:
    for pmcid, q in pmcids(ctx, env):
        if not env.room("pmc"):
            return
        num = pmcid.replace("PMC", "")
        summ = env.http.json(f"{EUTILS}/esummary.fcgi",
                             params=eparams(env, db="pmc", id=num,
                                            retmode="json")) or {}
        rec = flatten(summ.get("result", {}).get(num, {}))
        oa = env.http.text("https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
                           params={"id": pmcid})
        m = re.search(r'href="([^"]+)"', oa)
        rec["oa_package"] = m.group(1) if m else ""
        rec["oa_available"] = str(bool(m))
        rec["pmcid"] = pmcid
        yield Record("pmc", ctx.nct_id, q, pmcid, rec)


@source("pmc_bioc")
def s_pmc_bioc(ctx: TrialContext, env: Env) -> Iterable[Record]:
    """Full text section by section. Open-access subset only; others return an
    error document, which we skip."""
    if not env.full_text:
        return
    for pmcid, q in pmcids(ctx, env):
        if not env.room("pmc_bioc"):
            return
        d = env.http.json(f"{BIOC}/BioC_json/{pmcid}/unicode")
        if not d:
            continue
        docs = d[0].get("documents", []) if isinstance(d, list) else d.get("documents", [])
        for doc in docs:
            passages = doc.get("passages", [])
            rec = {"pmcid": pmcid, "n_passages": str(len(passages))}
            for k, v in (doc.get("infons") or {}).items():
                rec[f"infon.{k}"] = str(v)[:1000]
            for i, p in enumerate(passages):
                infons = p.get("infons") or {}
                text = (p.get("text") or "").strip()
                if not text:
                    continue
                sec = infons.get("section_type", "BODY")
                typ = infons.get("type", "")
                for ci, part in chunk(text):
                    rec[f"p{i:03d}.{sec}.{typ}.{ci}"] = part
            yield Record("pmc_bioc", ctx.nct_id, q, pmcid, rec)


@probe("pmc_bioc")
def p_bioc(env: Env) -> str:
    d = env.http.json(f"{BIOC}/BioC_json/PMC6692298/unicode", use_cache=False)
    return "ok" if d else "no data"


# ──────────────────────────────────── Europe PMC / OpenAlex / Crossref
@source("europepmc")
def s_europepmc(ctx: TrialContext, env: Env) -> Iterable[Record]:
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    q = f'"{ctx.nct_id}"'
    d = env.http.json(url, params={"query": q, "format": "json",
                                   "pageSize": env.per_source_limit,
                                   "resultType": "core"}) or {}
    for r in d.get("resultList", {}).get("result", []):
        yield Record("europepmc", ctx.nct_id, q, r.get("id", "?"), flatten(r))


@probe("europepmc")
def p_epmc(env: Env) -> str:
    d = env.http.json("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                      params={"query": "pexiganan", "format": "json", "pageSize": 1},
                      use_cache=False) or {}
    return "ok" if d.get("resultList") else "no results"


@source("openalex")
def s_openalex(ctx: TrialContext, env: Env) -> Iterable[Record]:
    q = ctx.nct_id
    d = env.http.json("https://api.openalex.org/works",
                      params={"search": q, "mailto": env.email,
                              "per-page": min(env.per_source_limit, 50)}) or {}
    for w in d.get("results", []):
        abstract = oa_abstract(w.pop("abstract_inverted_index", None))
        rec = flatten(w)
        if abstract:
            rec["abstract"] = abstract[:MAX_VAL]
        yield Record("openalex", ctx.nct_id, q,
                     (w.get("id") or "").rsplit("/", 1)[-1], rec)


@source("crossref")
def s_crossref(ctx: TrialContext, env: Env) -> Iterable[Record]:
    q = ctx.nct_id
    d = env.http.json("https://api.crossref.org/works",
                      params={"query.bibliographic": q, "mailto": env.email,
                              "rows": min(env.per_source_limit, 20)}) or {}
    for it in d.get("message", {}).get("items", []):
        it.pop("reference", None)
        yield Record("crossref", ctx.nct_id, q, it.get("DOI", "?"), flatten(it))


# ───────────────────────────────────────────── UniProt / EBI Proteins
@source("uniprot")
def s_uniprot(ctx: TrialContext, env: Env) -> Iterable[Record]:
    url = "https://rest.uniprot.org/uniprotkb/search"
    for term in ctx.terms[:6]:
        if not env.room("uniprot"):
            return
        d = env.http.json(url, params={"query": f'"{term}"', "format": "json",
                                       "size": min(env.per_source_limit, 500)}) or {}
        for r in d.get("results", []):
            yield Record("uniprot", ctx.nct_id, term,
                         r.get("primaryAccession", "?"), flatten(r))
    for seq in ctx.sequences:
        if not env.room("uniprot"):
            return
        d = env.http.json(url, params={"query": f'sequence:"{seq}"',
                                       "format": "json", "size": 10}) or {}
        for r in d.get("results", []):
            yield Record("uniprot", ctx.nct_id, f"seq:{seq[:20]}",
                         r.get("primaryAccession", "?"), flatten(r))


@probe("uniprot")
def p_uniprot(env: Env) -> str:
    d = env.http.json("https://rest.uniprot.org/uniprotkb/search",
                      params={"query": "cathelicidin", "format": "json", "size": 1},
                      use_cache=False) or {}
    return "ok" if d.get("results") else "no results"


@source("ebi_proteins")
def s_ebi_proteins(ctx: TrialContext, env: Env) -> Iterable[Record]:
    base = "https://www.ebi.ac.uk/proteins/api"
    hdr = {"Accept": "application/json"}
    for term in ctx.terms[:6]:
        if not (env.room("ebi_proteins") or env.room("ebi_proteins_features")):
            return
        d = env.http.json(f"{base}/proteins",
                          params={"offset": 0, "protein": term,
                                  "size": min(env.per_source_limit, 100)},
                          headers=hdr)
        for r in (d or []):
            acc = r.get("accession", "?")
            if env.room("ebi_proteins"):
                yield Record("ebi_proteins", ctx.nct_id, term, acc, flatten(r))
            if not env.room("ebi_proteins_features"):
                continue
            f = env.http.json(f"{base}/features/{acc}", headers=hdr)
            if f:
                yield Record("ebi_proteins_features", ctx.nct_id, term, acc,
                             flatten(f))


@probe("ebi_proteins")
def p_ebip(env: Env) -> str:
    d = env.http.json("https://www.ebi.ac.uk/proteins/api/proteins",
                      params={"offset": 0, "size": 1, "protein": "cathelicidin"},
                      headers={"Accept": "application/json"}, use_cache=False)
    return "ok" if d else "no data"


# ────────────────────────────────────────────── ChEMBL / IUPHAR / DBAASP
@source("chembl")
def s_chembl(ctx: TrialContext, env: Env) -> Iterable[Record]:
    lim = min(env.per_source_limit, 100)
    for term in ctx.terms[:6]:
        if env.room("chembl") or env.room("chembl_activity"):
            d = env.http.json(f"{CHEMBL}/molecule/search",
                              params={"q": term, "format": "json",
                                      "limit": lim}) or {}
            for m in d.get("molecules", []):
                cid = m.get("molecule_chembl_id", "?")
                if env.room("chembl"):
                    yield Record("chembl", ctx.nct_id, term, cid, flatten(m))
                # bioactivities are where the MIC / IC50 numbers live
                if not env.room("chembl_activity"):
                    continue
                act = env.http.json(f"{CHEMBL}/activity",
                                    params={"molecule_chembl_id": cid,
                                            "format": "json", "limit": lim}) or {}
                for a in act.get("activities", []):
                    yield Record("chembl_activity", ctx.nct_id, term,
                                 str(a.get("activity_id", "?")), flatten(a))
        if env.room("chembl_indication"):
            ind = env.http.json(f"{CHEMBL}/drug_indication/search",
                                params={"q": term, "format": "json",
                                        "limit": lim}) or {}
            for di in ind.get("drug_indications", []):
                yield Record("chembl_indication", ctx.nct_id, term,
                             str(di.get("drugind_id", "?")), flatten(di))


@probe("chembl")
def p_chembl(env: Env) -> str:
    d = env.http.json(f"{CHEMBL}/molecule/search",
                      params={"q": "aspirin", "format": "json", "limit": 1},
                      use_cache=False) or {}
    return "ok" if d.get("molecules") else "no results"


@source("iuphar")
def s_iuphar(ctx: TrialContext, env: Env) -> Iterable[Record]:
    subs = ("interactions", "synonyms")
    for term in ctx.terms[:6]:
        if not (env.room("iuphar")
                or any(env.room(f"iuphar_{s}") for s in subs)):
            return
        for kind, path, key in (("ligand", "/ligands", "ligandId"),
                                ("target", "/targets", "targetId")):
            rows = env.http.json(f"{GTOP}{path}", params={"name": term}) or []
            if isinstance(rows, dict):
                rows = [rows]
            for r in rows[: env.per_source_limit]:
                rid = str(r.get(key, "?"))
                rec = flatten(r)
                rec["_kind"] = kind
                if env.room("iuphar"):
                    yield Record("iuphar", ctx.nct_id, term, f"{kind}:{rid}", rec)
                if kind == "ligand" and rid != "?":
                    for sub in subs:
                        if not env.room(f"iuphar_{sub}"):
                            continue
                        extra = env.http.json(f"{GTOP}/ligands/{rid}/{sub}")
                        if extra:
                            yield Record(f"iuphar_{sub}", ctx.nct_id, term, rid,
                                         flatten(extra))


@probe("iuphar")
def p_gtop(env: Env) -> str:
    d = env.http.json(f"{GTOP}/ligands", params={"name": "LL-37"}, use_cache=False)
    return "ok" if d is not None else "no data"


@source("dbaasp")
def s_dbaasp(ctx: TrialContext, env: Env) -> Iterable[Record]:
    """Keyless DBAASP v3/v4. OpenAPI spec: https://dbaasp.org/v3/api-docs"""
    hdr = {"Accept": "application/json"}

    def emit(payload, query):
        rows = payload
        if isinstance(payload, dict):
            rows = (payload.get("data") or payload.get("content")
                    or payload.get("peptides") or [])
            if not rows and payload.get("id"):
                rows = [payload]
        for i, r in enumerate(rows or []):
            rid = str(r.get("id") or r.get("peptideId") or f"dbaasp{i:03d}")
            yield Record("dbaasp", ctx.nct_id, query, rid, flatten(r))

    for term in ctx.terms[:6]:
        if not env.room("dbaasp"):
            return
        d = env.http.json(f"{DBAASP}/peptides",
                          params={"name": term, "offset": 0,
                                  "limit": min(env.per_source_limit, 100)},
                          headers=hdr)
        yield from emit(d, f"name:{term}")

    for seq in ctx.sequences:
        if not env.room("dbaasp"):
            return
        d = env.http.json(f"{DBAASP}/peptides",
                          params={"sequence": seq, "offset": 0,
                                  "limit": env.per_source_limit},
                          headers=hdr)
        yield from emit(d, f"sequence:{seq[:20]}")


@probe("dbaasp")
def p_dbaasp(env: Env) -> str:
    d = env.http.json(f"{DBAASP}/peptides", params={"limit": 1, "offset": 0},
                      headers={"Accept": "application/json"}, use_cache=False)
    return "ok" if d is not None else "no JSON (check /v3/api-docs for param drift)"


# ─────────────────────────────────────────── RCSB / PDBe / IntAct
@source("rcsb_pdb")
def s_rcsb(ctx: TrialContext, env: Env) -> Iterable[Record]:
    for term in ctx.terms[:6]:
        if not env.room("rcsb_pdb"):
            return
        query = {
            "query": {"type": "terminal", "service": "full_text",
                      "parameters": {"value": term}},
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": min(env.per_source_limit, 100)},
                "results_verbosity": "compact"},
        }
        d = env.http.json("https://search.rcsb.org/rcsbsearch/v2/query",
                          params={"json": json.dumps(query)}) or {}
        ids = [i if isinstance(i, str) else i.get("identifier", "")
               for i in (d.get("result_set") or [])]
        for pdb_id in ids[: env.per_source_limit]:
            if not pdb_id:
                continue
            if not env.room("rcsb_pdb"):
                return
            entry = env.http.json(
                f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}") or {}
            rec = flatten(entry)
            rec["pdb_id"] = pdb_id
            yield Record("rcsb_pdb", ctx.nct_id, term, pdb_id, rec)


@probe("rcsb_pdb")
def p_rcsb(env: Env) -> str:
    d = env.http.json("https://data.rcsb.org/rest/v1/core/entry/1A2M",
                      use_cache=False)
    return "ok" if d else "no data"


@source("pdbe")
def s_pdbe(ctx: TrialContext, env: Env) -> Iterable[Record]:
    for term in ctx.terms[:6]:
        if not env.room("pdbe"):
            return
        d = env.http.json(
            "https://www.ebi.ac.uk/pdbe/search/pdb/select",
            params={"q": f'"{term}"', "wt": "json",
                    "rows": min(env.per_source_limit, 100),
                    "fl": ("pdb_id,title,molecule_name,experimental_method,"
                           "resolution,release_date,uniprot_accession,"
                           "organism_scientific_name,compound_name,"
                           "citation_title,journal,pubmed_id")}) or {}
        for doc in d.get("response", {}).get("docs", []):
            if not env.room("pdbe"):
                return
            pdb_id = doc.get("pdb_id", "?")
            rec = flatten(doc)
            summ = env.http.json(
                f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary/{pdb_id}") or {}
            rec.update({f"summary.{k}": v for k, v in flatten(summ).items()})
            yield Record("pdbe", ctx.nct_id, term, pdb_id, rec)


@probe("pdbe")
def p_pdbe(env: Env) -> str:
    d = env.http.json("https://www.ebi.ac.uk/pdbe/search/pdb/select",
                      params={"q": '"defensin"', "wt": "json", "rows": 1},
                      use_cache=False) or {}
    return "ok" if d.get("response") else "no results"


@source("intact")
def s_intact(ctx: TrialContext, env: Env) -> Iterable[Record]:
    base = "https://www.ebi.ac.uk/intact/ws/interaction"
    for term in ctx.terms[:6]:
        if not env.room("intact"):
            return
        d = env.http.json(f"{base}/findInteractions/{urllib.parse.quote(term)}",
                          params={"page": 0,
                                  "pageSize": min(env.per_source_limit, 100)},
                          headers={"Accept": "application/json"}) or {}
        rows = d.get("content", d if isinstance(d, list) else [])
        for i, r in enumerate(rows):
            rid = str(r.get("interactionAc") or r.get("idA") or f"intact{i:03d}")
            yield Record("intact", ctx.nct_id, term, rid, flatten(r))


@probe("intact")
def p_intact(env: Env) -> str:
    d = env.http.json(
        "https://www.ebi.ac.uk/intact/ws/interaction/findInteractions/CAMP",
        params={"page": 0, "pageSize": 1},
        headers={"Accept": "application/json"}, use_cache=False)
    return "ok" if d is not None else "no data"


# ───────────────────────────────────────────────────────────────── output
def oa_abstract(index: dict | None) -> str:
    """OpenAlex ships abstracts as {word: [positions]}; rebuild the text."""
    if not index:
        return ""
    pos: dict[int, str] = {}
    for word, locs in index.items():
        for loc in locs:
            pos[loc] = word
    return " ".join(pos[k] for k in sorted(pos))


_TAGS = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = _TAGS.sub(" ", text or "")            # Crossref ships JATS XML
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^abstract[:\s]*", "", text, flags=re.I)


# flattened field names holding each value, per source, best first
ABSTRACT_KEYS = {
    "abstract": ["abstract", "abstractText"],
    "title": ["title", "ArticleTitle"],
    "pmid": ["pmid", "ids.pmid"],
    "pmcid": ["pmcid", "pmcid.value"],
    "doi": ["doi", "DOI", "ids.doi"],
    "journal": ["journal", "journalInfo.journal.title", "container-title",
                "primary_location.source.display_name"],
    "year": ["year", "pubYear", "publication_year",
             "journalInfo.yearOfPublication"],
}


def _pick(fields: dict, names: list) -> str:
    for n in names:
        v = fields.get(n)
        if v:
            return str(v)
    return ""


def abstract_row(rec: Record) -> dict | None:
    """Normalise any literature record down to one tidy abstract row."""
    text = _clean(_pick(rec.fields, ABSTRACT_KEYS["abstract"]))
    if len(text) < 40:          # empty, or a stub like "No abstract available"
        return None
    row = {"nct_id": rec.nct_id, "source": rec.source, "abstract": text}
    for col in ("pmid", "pmcid", "doi", "title", "journal", "year"):
        row[col] = _clean(_pick(rec.fields, ABSTRACT_KEYS[col]))[:500]
    row["doi"] = row["doi"].replace("https://doi.org/", "").lower()
    return row


class AbstractWriter:
    """--abstracts mode: one flat abstracts.csv, deduped per trial. Same
    interface as Writer so the runner doesn't care which one it got."""

    COLS = ["nct_id", "pmid", "pmcid", "doi", "year", "journal", "title",
            "source", "abstract"]

    def __init__(self, out_dir: str, append: bool = False):
        path = os.path.join(out_dir, "abstracts.csv")
        exists = append and os.path.exists(path) and os.path.getsize(path) > 0
        if exists:
            ensure_newline(path)
        self._f = open(path, "a" if exists else "w", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._f, fieldnames=self.COLS,
                                 extrasaction="ignore")
        if not exists:
            self._w.writeheader()
        self.seen: set = set()
        self.counts: dict[str, int] = {}

    def write(self, rec: Record):
        row = abstract_row(rec)
        if not row:
            return
        key = (row["nct_id"], row["doi"] or row["pmid"] or row["pmcid"]
               or row["title"][:80].lower())
        if key in self.seen:
            return                      # same paper via a second source
        self.seen.add(key)
        self._w.writerow(row)
        self.counts[rec.source] = self.counts.get(rec.source, 0) + 1

    def tick(self, force: bool = False):
        try:
            self._f.flush()
        except (OSError, ValueError):
            pass

    def close(self):
        self._f.close()


class CombinedWriter:
    """Routes each record by source: abstract-bearing ones get tidied into
    abstracts.csv, everything else keeps the full long/wide treatment. Either
    file is only created if something actually lands in it."""

    def __init__(self, out_dir: str, append: bool = False,
                 abstract_sources: Iterable = (), wide: bool = True):
        self.out_dir = out_dir
        self.append = append
        self.wide = wide
        self.abs_srcs = set(abstract_sources)
        self._a = None
        self._r = None

    def write(self, rec: Record):
        if rec.source in self.abs_srcs:
            if self._a is None:
                self._a = AbstractWriter(self.out_dir, self.append)
            self._a.write(rec)
        else:
            if self._r is None:
                self._r = Writer(self.out_dir, self.append, wide=self.wide)
            self._r.write(rec)

    @property
    def counts(self) -> dict:
        out = dict(self._a.counts) if self._a else {}
        if self._r:
            out.update(self._r.counts)
        return out

    def tick(self, force: bool = False):
        for w in (self._a, self._r):
            if w is not None:
                w.tick(force)

    def files(self) -> list:
        f = []
        if self._a:
            f.append("abstracts.csv")
        if self._r:
            f.append("records_long.csv")
            if self.wide:
                f.append("by_source/*.csv")
        return f

    def close(self):
        for w in (self._a, self._r):
            if w:
                w.close()


class Writer:
    """Long-format master CSV plus one wide CSV per source."""

    LONG_COLS = ["nct_id", "source", "query", "record_id", "field", "value",
                 "retrieved_at"]

    SPILL_ROWS = 20000     # buffered wide rows before writing a part file

    def __init__(self, out_dir: str, append: bool = False, wide: bool = True):
        self.out_dir = out_dir
        self.append = append
        self.wide = wide
        os.makedirs(os.path.join(out_dir, "by_source") if wide else out_dir,
                    exist_ok=True)
        path = os.path.join(out_dir, "records_long.csv")
        exists = append and os.path.exists(path) and os.path.getsize(path) > 0
        if exists:
            ensure_newline(path)
        self._f = open(path, "a" if exists else "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        if not exists:
            self._w.writerow(self.LONG_COLS)
        self._wide: dict[str, list[dict]] = {}
        self._buffered = 0
        self.counts: dict[str, int] = {}

    def write(self, rec: Record):
        ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for k, v in rec.fields.items():
            self._w.writerow([rec.nct_id, rec.source, rec.query, rec.record_id,
                              k, v, ts])
        self.counts[rec.source] = self.counts.get(rec.source, 0) + 1
        if not self.wide:
            return
        row = {"nct_id": rec.nct_id, "query": rec.query,
               "record_id": rec.record_id}
        row.update(rec.fields)
        self._wide.setdefault(rec.source, []).append(row)
        self._buffered += 1

    def _wide_path(self, name: str) -> str:
        """First write takes <name>.csv; later spills and resumed segments take
        <name>.partN.csv, since column sets differ between batches."""
        base = os.path.join(self.out_dir, "by_source", f"{name}.csv")
        if not os.path.exists(base):
            return base
        i = 2
        while os.path.exists(os.path.join(self.out_dir, "by_source",
                                          f"{name}.part{i}.csv")):
            i += 1
        return os.path.join(self.out_dir, "by_source", f"{name}.part{i}.csv")

    def tick(self, force: bool = False):
        """Between trials: flush the long CSV and spill the wide buffer, so a
        crash costs the last trial rather than the whole run."""
        try:
            self._f.flush()
        except (OSError, ValueError):
            pass
        if not self.wide or not self._wide:
            return
        if not force and self._buffered < self.SPILL_ROWS:
            return
        for name, rows in self._wide.items():
            if not rows:
                continue
            cols: list[str] = []
            for r in rows:
                for k in r:
                    if k not in cols:
                        cols.append(k)
            with open(self._wide_path(name), "w", newline="",
                      encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        self._wide.clear()
        self._buffered = 0

    def close(self):
        self.tick(force=True)
        self._f.close()


def read_ncts(path: str, id_col: str | None, seq_col: str | None):
    """A proper CSV, or any text file with NCT ids in it."""
    out: list[tuple[str, list[str]]] = []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        head = f.read(4096)
        f.seek(0)
        if "," in head or "\t" in head:
            delim = "\t" if head.count("\t") > head.count(",") else ","
            rdr = csv.DictReader(f, delimiter=delim)
            cols = rdr.fieldnames or []
            col = id_col or next(
                (c for c in cols if c and c.strip().lower() in
                 {"nct_id", "nctid", "nct", "nct number", "nct_number", "id"}), None)
            if col:
                for row in rdr:
                    m = NCT_RE.search(str(row.get(col, "")))
                    if not m:
                        continue
                    seqs = []
                    if seq_col and row.get(seq_col):
                        seqs = [s.strip().upper() for s in
                                re.split(r"[;,|\s]+", row[seq_col])
                                if len(s.strip()) > 5]
                    out.append((m.group(0).upper(), seqs))
                if out:
                    return _dedupe(out)
        f.seek(0)
        out = [(m.group(0).upper(), []) for m in NCT_RE.finditer(f.read())]
    return _dedupe(out)


def ensure_newline(path: str):
    """A crash mid-write (out of disk, kill -9) can leave the last line without
    its newline. Appending onto that would fuse two rows, so terminate it."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return
    with open(path, "rb+") as f:
        f.seek(-1, os.SEEK_END)
        if f.read(1) != b"\n":
            f.write(b"\n")
            print(f"repaired truncated last line in {path}", file=sys.stderr)


MAX_WIDE_COLS = 500   # beyond this a wide CSV is mostly empty commas

# Fields worth putting in front of a model, per source. Matched as substrings
# of the flattened field name, so "conditions" catches
# "protocolSection.conditionsModule.conditions". Everything else is dropped:
# a UniProt record has thousands of fields and maybe eight that matter here.
PACK_FIELDS = {
    "clinicaltrials": [
        "briefTitle", "officialTitle", "overallStatus", "phases", "studyType",
        "enrollmentInfo.count", "conditions", "keywords", "interventions",
        "briefSummary", "primaryOutcomes", "leadSponsor.name",
        "startDateStruct.date", "completionDateStruct.date",
        "designInfo.allocation", "designInfo.primaryPurpose",
        "eligibilityModule.sex", "eligibilityModule.minimumAge",
        "whyStopped"],
    "uniprot": [
        "primaryAccession", "recommendedName.fullName.value",
        "organism.scientificName", "sequence.value", "sequence.length",
        "proteinExistence"],
    "ebi_proteins": [
        "accession", "recommendedName.fullName.value", "organism.names",
        "sequence.sequence", "sequence.length"],
    "ebi_proteins_features": ["type", "description", "begin", "end"],
    "chembl": [
        "molecule_chembl_id", "pref_name", "max_phase", "molecule_type",
        "first_approval", "indication_class", "molecule_synonyms"],
    "chembl_activity": [
        "standard_type", "standard_value", "standard_units",
        "standard_relation", "target_pref_name", "target_organism",
        "assay_description"],
    "chembl_indication": ["mesh_heading", "efo_term", "max_phase_for_ind"],
    "dbaasp": [
        "name", "sequence", "targetActivities", "targetGroups",
        "unusualAminoAcids", "synthesisType"],
    "rcsb_pdb": [
        "pdb_id", "struct.title", "exptl", "resolution_combined",
        "rcsb_entry_info.polymer_composition"],
    "pdbe": [
        "pdb_id", "title", "molecule_name", "experimental_method",
        "resolution", "organism_scientific_name", "uniprot_accession"],
    "intact": [
        "moleculeA", "moleculeB", "idA", "idB", "interactionType",
        "interactionDetectionMethod", "organism"],
    "iuphar": ["name", "type", "approved", "species", "_kind"],
    "iuphar_interactions": ["targetName", "type", "affinity", "action"],
    "openfda": [
        "_endpoint", "generic_name", "brand_name", "substance_name",
        "indications_and_usage", "warnings", "clinical_studies"],
}

DEFAULT_PROMPT = """You are annotating a clinical trial for an antimicrobial \
peptide research database.

Using only the evidence below, return a JSON object with these keys:
  is_peptide_therapeutic: true/false
  peptide_names: list of peptide or biologic names under study, [] if none
  sequence: amino acid sequence if one appears in the evidence, else null
  indication: the condition treated, as a short phrase
  pathogen_targets: list of organisms targeted, [] if not antimicrobial
  phase: trial phase
  outcome: one of succeeded / failed / terminated / ongoing / unknown
  evidence_quality: high / medium / low, reflecting how much the sources agree
  notes: one sentence, or null

Return only the JSON object. Where the evidence is silent, use null or an \
empty list rather than guessing."""


def pack_bundles(out_dir: str, max_chars: int = 24000,
                 max_abstracts: int = 5) -> int:
    """Turn records_long.csv + abstracts.csv into one compact dossier per
    trial, small enough to be a single model prompt."""
    long_path = os.path.join(out_dir, "records_long.csv")
    abs_path = os.path.join(out_dir, "abstracts.csv")
    if not os.path.exists(long_path) and not os.path.exists(abs_path):
        print(f"need records_long.csv or abstracts.csv in {out_dir}",
              file=sys.stderr)
        return 2

    # pass 1: abstracts, trimmed, capped per trial
    abstracts: dict = {}
    if os.path.exists(abs_path):
        with open(abs_path, newline="", encoding="utf-8",
                  errors="replace") as f:
            for r in csv.DictReader(f):
                lst = abstracts.setdefault(r["nct_id"], [])
                if len(lst) < max_abstracts:
                    lst.append((r.get("pmid") or r.get("doi") or "",
                                r.get("year", ""), r.get("title", ""),
                                (r.get("abstract") or "")[:1500]))

    def wanted(source: str, field: str) -> bool:
        pats = PACK_FIELDS.get(source)
        return bool(pats) and any(p in field for p in pats)

    GENERIC = {"value", "name", "id", "text", "title", "sequence", "names"}

    def label(field: str) -> str:
        """Last segment, unless it's generic -- then the last two, so
        recommendedName.fullName.value and sequence.value stay distinct."""
        parts = [x for x in field.replace("[", ".").replace("]", "")
                 .split(".") if x and not x.isdigit()]
        if not parts:
            return field
        if len(parts) > 1 and parts[-1] in GENERIC:
            return ".".join(parts[-2:])
        return parts[-1]

    def render(nct: str, trial: dict, mol: dict) -> str:
        out = [f"# {nct}"]
        if trial:
            out.append("\n## Trial registration")
            for k, v in trial.items():
                out.append(f"- {label(k)}: {v}")
        abs_list = abstracts.get(nct, [])
        if abs_list:
            out.append(f"\n## Literature ({len(abs_list)})")
            for ident, year, title, text in abs_list:
                out.append(f"\n### {title} ({year}) [{ident}]\n{text}")
        if mol:
            out.append("\n## Molecular evidence")
            for src in sorted(mol):
                out.append(f"\n### {src}")
                for rid, fields in mol[src].items():
                    bits = "; ".join(f"{label(k)}={v}"
                                     for k, v in fields.items())
                    out.append(f"- [{rid}] {bits}")
        text = "\n".join(out)
        return text[:max_chars]

    dest = os.path.join(out_dir, "bundles.jsonl")
    n = 0
    sizes = []
    with open(dest, "w", encoding="utf-8") as outf:
        cur = None
        trial: dict = {}
        mol: dict = {}

        def flush():
            nonlocal n
            if not cur:
                return
            text = render(cur, trial, mol)
            outf.write(json.dumps({"nct_id": cur, "text": text},
                                  ensure_ascii=False) + "\n")
            sizes.append(len(text))
            n += 1

        seen = set()
        if os.path.exists(long_path):
            with open(long_path, newline="", encoding="utf-8",
                      errors="replace") as f:
                for r in csv.DictReader(f):
                    nct, src, fld = r["nct_id"], r["source"], r["field"]
                    if nct != cur:
                        flush()
                        seen.add(nct)
                        cur, trial, mol = nct, {}, {}
                    if not wanted(src, fld):
                        continue
                    if src == "clinicaltrials":
                        trial[fld] = r["value"][:600]
                    else:
                        recs = mol.setdefault(src, {})
                        if len(recs) < 5 or r["record_id"] in recs:
                            recs.setdefault(r["record_id"], {})[fld] = \
                                r["value"][:300]
            flush()
        # trials that produced only abstracts, through the same handle
        for nct in abstracts:
            if nct in seen:
                continue
            text = render(nct, {}, {})
            outf.write(json.dumps({"nct_id": nct, "text": text},
                                  ensure_ascii=False) + "\n")
            sizes.append(len(text))
            n += 1

    if sizes:
        sizes.sort()
        avg = sum(sizes) / len(sizes)
        print(f"{n} bundles -> {dest}", file=sys.stderr)
        print(f"chars: median {sizes[len(sizes) // 2]:,}  mean {avg:,.0f}  "
              f"max {sizes[-1]:,}", file=sys.stderr)
        print(f"rough total input tokens: {sum(sizes) / 3.8:,.0f}",
              file=sys.stderr)
    return 0


def export_bundles(out_dir: str, per_chunk: int = 0, limit: int = 0,
                   only: str | None = None) -> int:
    """Write bundles.jsonl out as markdown: one file per trial, and optionally
    chunks of N trials for uploading to a Project or a chat. For people driving
    Claude Code or claude.ai on a subscription rather than the API."""
    src = os.path.join(out_dir, "bundles.jsonl")
    if not os.path.exists(src):
        print(f"run --pack first ({src} missing)", file=sys.stderr)
        return 2

    keep = None
    if only:
        with open(only, newline="", encoding="utf-8", errors="replace") as f:
            keep = {m.group(0).upper() for m in NCT_RE.finditer(f.read())}
        print(f"filtering to {len(keep)} ids from {only}", file=sys.stderr)

    md_dir = os.path.join(out_dir, "bundles_md")
    os.makedirs(md_dir, exist_ok=True)
    chunk_dir = os.path.join(out_dir, "bundles_chunks")
    if per_chunk:
        os.makedirs(chunk_dir, exist_ok=True)

    n, ci, buf, buf_chars = 0, 1, [], 0
    for line in open(src, encoding="utf-8"):
        b = json.loads(line)
        if keep is not None and b["nct_id"] not in keep:
            continue
        with open(os.path.join(md_dir, f"{b['nct_id']}.md"), "w",
                  encoding="utf-8") as f:
            f.write(b["text"])
        n += 1
        if per_chunk:
            buf.append(b["text"])
            buf_chars += len(b["text"])
            if len(buf) >= per_chunk:
                with open(os.path.join(chunk_dir, f"chunk_{ci:03d}.md"), "w",
                          encoding="utf-8") as f:
                    f.write("\n\n---\n\n".join(buf))
                ci += 1
                buf, buf_chars = [], 0
        if limit and n >= limit:
            break
    if per_chunk and buf:
        with open(os.path.join(chunk_dir, f"chunk_{ci:03d}.md"), "w",
                  encoding="utf-8") as f:
            f.write("\n\n---\n\n".join(buf))

    print(f"{n} markdown files -> {md_dir}", file=sys.stderr)
    if per_chunk:
        print(f"{ci} chunk file(s) of up to {per_chunk} trials -> {chunk_dir}",
              file=sys.stderr)
    return 0


def write_batches(out_dir: str, model: str, prompt_path: str | None = None,
                  max_tokens: int = 1024, per_file: int = 9000,
                  max_bytes: int = 28 * 1024 * 1024) -> int:
    """Turn bundles.jsonl into Message Batches API request files. A batch is
    capped at 10,000 requests or 32 MB, so we chunk below both."""
    src = os.path.join(out_dir, "bundles.jsonl")
    if not os.path.exists(src):
        print(f"run --pack first ({src} missing)", file=sys.stderr)
        return 2
    prompt = DEFAULT_PROMPT
    if prompt_path:
        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()

    files, n, idx = [], 0, 1
    out, size = None, 0

    def open_next():
        nonlocal out, size, idx
        if out:
            out.close()
        path = os.path.join(out_dir, f"batch_{idx:03d}.jsonl")
        files.append(path)
        out = open(path, "w", encoding="utf-8")
        size = 0
        idx += 1

    open_next()
    with open(src, encoding="utf-8") as f:
        for line in f:
            b = json.loads(line)
            req = {
                "custom_id": b["nct_id"],
                "params": {
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": prompt,
                    "messages": [{"role": "user", "content": b["text"]}],
                },
            }
            blob = json.dumps(req, ensure_ascii=False) + "\n"
            if n and (n % per_file == 0 or size + len(blob) > max_bytes):
                open_next()
                n = 0
            out.write(blob)
            size += len(blob)
            n += 1
    out.close()
    for p_ in files:
        print(f"  {p_}  {os.path.getsize(p_) / 1e6:.1f} MB", file=sys.stderr)
    print(f"\n{len(files)} batch file(s). Submit each with the Message "
          f"Batches API.", file=sys.stderr)
    return 0


def rebuild(out_dir: str, fmt: str = "jsonl") -> int:
    """Regenerate per-source files from records_long.csv, which is the master.
    Recovers output after a crash with no refetching.

    jsonl (default): one JSON object per record, only the fields that record
    actually has. CSV: a column union per source, which for array-heavy sources
    like UniProt means tens of thousands of near-empty columns, so those are
    skipped. Streams; all fields of one record are contiguous in the long file.
    """
    src = os.path.join(out_dir, "records_long.csv")
    if not os.path.exists(src):
        print(f"no {src}", file=sys.stderr)
        return 2
    dest = os.path.join(out_dir, "by_source")
    os.makedirs(dest, exist_ok=True)

    cols: dict = {}
    if fmt == "csv":
        with open(src, newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                c = cols.setdefault(r["source"],
                                    ["nct_id", "query", "record_id"])
                if r["field"] not in c:
                    c.append(r["field"])
        if not cols:
            print("records_long.csv has no rows", file=sys.stderr)
            return 2
        print("sources: " + ", ".join(f"{k} ({len(v) - 3} cols)"
                                      for k, v in sorted(cols.items())),
              file=sys.stderr)
        skip = {k for k, v in cols.items() if len(v) - 3 > MAX_WIDE_COLS}
        for k in sorted(skip):
            print(f"!! skipping {k}: {len(cols[k]) - 3} columns would be "
                  f"~{(len(cols[k]) - 3) // 1000}KB of empty commas per row. "
                  f"Use --format jsonl.", file=sys.stderr)
        cols = {k: v for k, v in cols.items() if k not in skip}
        if not cols:
            print("nothing left to write as CSV; rerun with --format jsonl",
                  file=sys.stderr)
            return 2

    handles: dict = {}
    writers: dict = {}
    counts: dict = {}

    def handle(name: str):
        if name not in handles:
            ext = "jsonl" if fmt == "jsonl" else "rebuilt.csv"
            handles[name] = open(os.path.join(dest, f"{name}.{ext}"), "w",
                                 newline="" if fmt == "csv" else None,
                                 encoding="utf-8")
            if fmt == "csv":
                writers[name] = csv.DictWriter(handles[name],
                                               fieldnames=cols[name],
                                               extrasaction="ignore")
                writers[name].writeheader()
            counts[name] = 0
        return handles[name]

    key = None
    row: dict = {}

    def emit():
        if not key or not row:
            return
        name = key[1]
        if fmt == "csv" and name not in cols:
            return
        f = handle(name)
        if fmt == "jsonl":
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            writers[name].writerow(row)
        counts[name] += 1

    with open(src, newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            k = (r["nct_id"], r["source"], r["record_id"])
            if k != key:
                emit()
                key = k
                row = {"nct_id": r["nct_id"], "query": r["query"],
                       "record_id": r["record_id"]}
            row[r["field"]] = r["value"]
        emit()

    for h in handles.values():
        h.close()
    for name in sorted(counts):
        print(f"  {name:<22} {counts[name]} records", file=sys.stderr)
    print(f"\nwrote {dest}/*." + ("jsonl" if fmt == "jsonl" else "rebuilt.csv"),
          file=sys.stderr)
    return 0


def preflight(out_dir: str, cache_path: str):
    """Fail now with a clear message rather than 1900 trials in."""
    cache_dir = os.path.dirname(os.path.abspath(cache_path)) or "."
    for label, d, must_exist in (("output dir", out_dir, True),
                                 ("cache dir", cache_dir, False)):
        if not os.path.isdir(d):
            if must_exist:
                raise SystemExit(f"{label} does not exist: {d}")
            # walk up to the nearest existing parent and check we could create it
            probe = d
            while probe and not os.path.isdir(probe):
                parent = os.path.dirname(probe)
                if parent == probe:
                    break
                probe = parent
            if not os.access(probe, os.W_OK):
                raise SystemExit(
                    f"{label} {d} does not exist and {probe} is not writable."
                    f"\nUse a path on local disk:  "
                    f"--cache /tmp/ampharvest-cache.sqlite")
            print(f"{label}: {d} (will be created)", file=sys.stderr)
            continue
        if not os.access(d, os.W_OK):
            raise SystemExit(f"{label} is not writable: {d}")
        try:
            st = os.statvfs(d)
            free_gb = st.f_bavail * st.f_frsize / 1e9
            kind = fs_type(d) or "unknown"
            print(f"{label}: {d}  ({kind}, {free_gb:.1f} GB free)",
                  file=sys.stderr)
            if free_gb < 2:
                print(f"!! only {free_gb:.1f} GB free on {d} - a large run will "
                      f"fill it", file=sys.stderr)
        except (AttributeError, OSError):
            pass


def finished_trials(log_path: str) -> set:
    """NCT ids with a _trial/done sentinel in an existing run log."""
    done = set()
    if not os.path.exists(log_path):
        return done
    with open(log_path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if row.get("source") == "_trial" and row.get("status") == "done":
                done.add(row.get("nct_id", ""))
    done.discard("")
    return done


def _dedupe(pairs):
    seen, uniq = set(), []
    for nct, seqs in pairs:
        if nct not in seen:
            seen.add(nct)
            uniq.append((nct, seqs))
    return uniq


# ───────────────────────────────────────────────────────────────────── cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="ampharvest",
        description="Query 16 free keyless biomedical APIs from a CSV of NCT ids. Keeps the top --limit records per source per trial.")
    ap.add_argument("-i", "--input", help="CSV containing NCT ids")
    ap.add_argument("-o", "--out", default="out", help="output directory")
    ap.add_argument("--id-col", help="column holding the NCT id (auto-detected)")
    ap.add_argument("--sequence-col",
                    help="optional column of peptide sequences for the "
                         "UniProt/DBAASP sequence lookups")
    ap.add_argument("-s", "--sources", default="all",
                    help="comma-separated source names, or a group: "
                         "abstracts, literature, proteins, trials, all. "
                         "e.g.  -s abstracts,proteins")
    ap.add_argument("--exclude", default="", help="comma-separated sources to skip")
    ap.add_argument("--list-sources", action="store_true")
    ap.add_argument("--rebuild-wide", action="store_true",
                    help="regenerate per-source files from an existing "
                         "records_long.csv in -o, then exit. No network.")
    ap.add_argument("--pack", action="store_true",
                    help="build one compact per-trial dossier in "
                         "bundles.jsonl from records_long.csv + abstracts.csv, "
                         "sized for a single model prompt. No network.")
    ap.add_argument("--pack-max-chars", type=int, default=24000,
                    help="cap per bundle (default 24000, roughly 6k tokens)")
    ap.add_argument("--pack-abstracts", type=int, default=5,
                    help="max abstracts per bundle (default 5)")
    ap.add_argument("--export-md", action="store_true",
                    help="write bundles.jsonl out as markdown: one file per "
                         "trial, for Claude Code or claude.ai on a "
                         "subscription (no API credits needed)")
    ap.add_argument("--export-chunk", type=int, default=0,
                    help="with --export-md, also group N trials per file for "
                         "uploading to a Project")
    ap.add_argument("--export-limit", type=int, default=0,
                    help="with --export-md, stop after N trials")
    ap.add_argument("--export-only",
                    help="with --export-md, keep only the NCT ids found in "
                         "this file (e.g. your triage hits)")
    ap.add_argument("--batch-model",
                    help="also write Message Batches API request files for "
                         "this model, e.g. claude-sonnet-4-6")
    ap.add_argument("--batch-max-tokens", type=int, default=2048,
                    help="max_tokens per batch request (default 2048; raise it "
                         "for thinking models, whose thinking bills as output)")
    ap.add_argument("--batch-prompt",
                    help="file holding the system prompt for --batch-model; "
                         "a generic AMP annotation prompt is used otherwise")
    ap.add_argument("--format", choices=("jsonl", "csv"), default="jsonl",
                    help="--rebuild-wide output: jsonl (default, compact) or "
                         "csv (skips sources with >%d columns)"
                         % MAX_WIDE_COLS)
    ap.add_argument("--selftest", action="store_true",
                    help="ping every source and exit")
    ap.add_argument("--email",
                    default=os.environ.get("AMPHARVEST_EMAIL",
                                           "anonymous@example.org"),
                    help="contact email (NCBI and OpenAlex ask for one)")
    ap.add_argument("--ncbi-key", default=os.environ.get("NCBI_API_KEY"),
                    help="free NCBI key: 3/s -> 10/s")
    ap.add_argument("--openfda-key", default=os.environ.get("OPENFDA_API_KEY"),
                    help="free openFDA key: 1k/day -> 120k/day")
    ap.add_argument("--limit", type=int, default=5,
                    help="max records kept per source per trial, and the page "
                         "size asked of each API (default 5)")
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel sources per trial; keep it low")
    ap.add_argument("--cache", default=".ampharvest-cache.sqlite")
    ap.add_argument("--cache-days", type=float, default=30.0)
    ap.add_argument("--no-full-text", action="store_true",
                    help="skip PMC BioC full text; output shrinks ~20x")
    ap.add_argument("--no-wide", action="store_true",
                    help="skip by_source/*.csv; records_long.csv holds the same "
                         "data, so this roughly halves disk use")
    ap.add_argument("--abstracts", action="store_true",
                    help="write the literature sources as one flat "
                         "abstracts.csv instead of full records. Defaults to "
                         "the literature sources alone; add others with -s "
                         "(e.g. -s abstracts,proteins) and they keep their "
                         "normal records_long/by_source output")
    ap.add_argument("--offline", action="store_true",
                    help="cache only, no network calls")
    ap.add_argument("--resume", action="store_true",
                    help="skip trials already finished in out/run_log.csv and "
                         "append to the existing output")
    ap.add_argument("--max-consecutive-errors", type=int, default=25,
                    help="abort if this many trials fail in a row (0 = never)")
    args = ap.parse_args(argv)

    if args.list_sources:
        print("\n".join(sorted(REGISTRY)))
        return 0

    if args.rebuild_wide:
        return rebuild(args.out, args.format)

    if args.export_md:
        return export_bundles(args.out, args.export_chunk, args.export_limit,
                              args.export_only)

    if args.pack:
        rc = pack_bundles(args.out, args.pack_max_chars, args.pack_abstracts)
        if rc == 0 and args.batch_model:
            rc = write_batches(args.out, args.batch_model, args.batch_prompt,
                               max_tokens=args.batch_max_tokens)
        return rc

    os.makedirs(args.out, exist_ok=True)
    preflight(args.out, args.cache)

    env = Env(
        http=Client(cache=Cache(args.cache, ttl_days=args.cache_days),
                    email=args.email, offline=args.offline),
        email=args.email,
        ncbi_api_key=args.ncbi_key,
        openfda_api_key=args.openfda_key,
        per_source_limit=args.limit,
        full_text=not args.no_full_text,
    )

    if args.selftest:
        print(f"{'source':<16} status")
        for name in sorted(PROBES):
            try:
                print(f"{name:<16} {PROBES[name](env)}")
            except Exception as e:
                print(f"{name:<16} FAIL: {str(e)[:90]}")
        return 0

    if not args.input:
        ap.error("--input is required (or use --selftest / --list-sources)")

    if args.sources == "all":
        wanted = (ABSTRACT_SOURCES if args.abstracts else sorted(REGISTRY))
    else:
        wanted = []
        for tok in (t.strip() for t in args.sources.split(",")):
            if not tok:
                continue
            if tok == "all":
                wanted += sorted(REGISTRY)
            elif tok in SOURCE_GROUPS:
                wanted += SOURCE_GROUPS[tok]
            else:
                wanted.append(tok)
        wanted = list(dict.fromkeys(wanted))   # dedupe, keep order
    skip = {s.strip() for s in args.exclude.split(",") if s.strip()}
    wanted = [s for s in wanted if s not in skip]
    unknown = [s for s in wanted if s not in REGISTRY]
    if unknown:
        ap.error(f"unknown sources: {', '.join(unknown)}")

    trials = read_ncts(args.input, args.id_col, args.sequence_col)
    if not trials:
        print(f"no NCT ids found in {args.input}", file=sys.stderr)
        return 2

    log_path = os.path.join(args.out, "run_log.csv")
    trials_path = os.path.join(args.out, "trials.csv")
    done = finished_trials(log_path) if args.resume else set()
    if done:
        before = len(trials)
        trials = [t for t in trials if t[0] not in done]
        print(f"resume: {len(done)} trials already finished, "
              f"{len(trials)} of {before} left", file=sys.stderr)
        if not trials:
            print("nothing left to do", file=sys.stderr)
            return 0

    print(f"{len(trials)} trials x {len(wanted)} sources"
          f"{' (abstracts only)' if args.abstracts else ''}", file=sys.stderr)
    writer = (CombinedWriter(args.out, append=args.resume,
                             abstract_sources=ABSTRACT_SOURCES,
                             wide=not args.no_wide)
              if args.abstracts
              else Writer(args.out, append=args.resume, wide=not args.no_wide))

    log_exists = args.resume and os.path.exists(log_path) \
        and os.path.getsize(log_path) > 0
    trials_exists = args.resume and os.path.exists(trials_path) \
        and os.path.getsize(trials_path) > 0
    consecutive = 0
    out_of_space = None

    for _p, _e in ((log_path, log_exists), (trials_path, trials_exists)):
        if _e:
            ensure_newline(_p)

    with open(log_path, "a" if log_exists else "w", newline="",
              encoding="utf-8") as logf, \
         open(trials_path, "a" if trials_exists else "w", newline="",
              encoding="utf-8") as tf:
        log = csv.writer(logf)
        if not log_exists:
            log.writerow(["nct_id", "source", "status", "n_records", "detail",
                          "ts"])
        tw = csv.writer(tf)
        if not trials_exists:
            tw.writerow(["nct_id", "title", "phases", "conditions",
                         "interventions", "search_terms", "sponsors",
                         "other_ids"])

        for n, (nct, seqs) in enumerate(trials, 1):
            ts = dt.datetime.now().isoformat(timespec="seconds")
            try:
                ctx = build_context(nct, env, seqs)
            except Exception as e:
                log.writerow([nct, "clinicaltrials", "error", 0, str(e)[:300], ts])
                logf.flush()
                print(f"[{n}/{len(trials)}] {nct} context FAILED: {e}",
                      file=sys.stderr)
                consecutive += 1
                if args.max_consecutive_errors and \
                        consecutive >= args.max_consecutive_errors:
                    print(f"\n!! aborting: {consecutive} trials failed in a row."
                          f"\n!! last error: {e}"
                          f"\n!! fix the cause, then rerun with --resume.\n",
                          file=sys.stderr)
                    break
                continue
            consecutive = 0
            tw.writerow([nct, ctx.title, " | ".join(ctx.phases),
                         " | ".join(ctx.conditions), " | ".join(ctx.interventions),
                         " | ".join(ctx.terms), " | ".join(ctx.sponsors),
                         " | ".join(ctx.other_ids)])
            tf.flush()
            print(f"[{n}/{len(trials)}] {nct}  terms={ctx.terms or '-'}",
                  file=sys.stderr)

            env.budget = Budget(args.limit)

            def run(name: str):
                kept = []
                for r in REGISTRY[name](ctx, env):
                    # in abstracts mode an abstract-less record shouldn't eat
                    # a slot in the budget -- but only for the sources that
                    # are supposed to have one
                    if (args.abstracts and r.source in ABSTRACT_SOURCES
                            and abstract_row(r) is None):
                        continue
                    if env.budget.take(r.source):
                        kept.append(r)
                return name, kept

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futs = {pool.submit(run, s): s for s in wanted}
                for fut in as_completed(futs):
                    name = futs[fut]
                    ts = dt.datetime.now().isoformat(timespec="seconds")
                    try:
                        name, recs = fut.result()
                    except Exception as e:
                        log.writerow([nct, name, "error", 0,
                                      f"{type(e).__name__}: {e}"[:300], ts])
                        print(f"    {name:<16} ERROR {type(e).__name__}: {e}",
                              file=sys.stderr)
                        if os.environ.get("AMPHARVEST_DEBUG"):
                            traceback.print_exc()
                        continue
                    try:
                        for r in recs:
                            writer.write(r)
                    except OSError as e:
                        out_of_space = e
                        break
                    log.writerow([nct, name, "ok", len(recs), "", ts])
                    print(f"    {name:<16} {len(recs)}", file=sys.stderr)
            if out_of_space is not None:
                print(f"\n!! {out_of_space}\n"
                      f"!! Out of disk writing to {args.out}. Trials up to "
                      f"{n - 1} are saved.\n"
                      f"!! Free space (or add --no-wide / --abstracts), then "
                      f"rerun the same command with --resume.\n",
                      file=sys.stderr)
                break
            # sentinel: --resume treats a trial as done only once this lands
            log.writerow([nct, "_trial", "done", 0, "",
                          dt.datetime.now().isoformat(timespec="seconds")])
            logf.flush()
            writer.tick()

    try:
        writer.close()
    except OSError as e:
        print(f"!! could not flush output: {e}", file=sys.stderr)
    print("\nrecords per source:", file=sys.stderr)
    for k in sorted(writer.counts):
        print(f"  {k:<22} {writer.counts[k]}", file=sys.stderr)
    made = (writer.files() if hasattr(writer, "files")
            else ["records_long.csv", "by_source/*.csv"])
    made += ["trials.csv", "run_log.csv"]
    print("\nwrote " + ", ".join(f"{args.out}/{f}" for f in made),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
