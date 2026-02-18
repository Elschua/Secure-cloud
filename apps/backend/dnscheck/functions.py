import dns.resolver
import dns.exception
import re
from enum import Enum
from typing import Optional, Dict, List, Set
import requests

# -------------------- CONSTANTS --------------------

class Codes(Enum):
    DOMAIN_NOT_FOUND = 1
    RECORD_NOT_FOUND = 2
    MULTIPLE_RECORDS_FOUND = 3
    DUPLICATE_RECORD_TERMS = 4
    RECORD_SYNTAX_ERROR = 5
    INVALID_DOMAIN = 7
    LOOKUPS_LIMIT = 8

resolver = dns.resolver.Resolver()
resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
resolver.timeout = 2.0
resolver.lifetime = 5.0

dkim_selectors = [
    '20161025','20210112','20220623','20230601','a','a1','acdkim1','amazonses','default','dkim','google'
    # ... tu peux ajouter d’autres selectors si besoin
]

MAX_LOOKUPS = 10

# -------------------- VALIDATORS --------------------

def validate_domain(domain: str) -> bool:
    """Validate domain format."""
    if not domain or len(domain) > 253:
        return False
    pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
        r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    )
    return bool(pattern.match(domain))

def parse_dmarc(dmarc_string: str) -> dict:
    """Parse DMARC record into key-value pairs."""
    result = dict(re.findall(r'(\w+)\s*=\s*([^;]+)', dmarc_string))
    result["raw"] = dmarc_string
    return result

def parse_spf(spf_string: str) -> dict:
    """
    Parse SPF record into components safely.
    Returns a dict with keys for tags and a 'raw' copy of the record.
    """
    result = {"raw": spf_string}
    
    if not spf_string:
        return result

    # Split record into parts
    for part in spf_string.strip().split():
        part = part.strip()
        if not part:
            continue

        # Match qualifier, tag, optional value
        m = re.fullmatch(r'([+\-~?]?)([a-zA-Z0-9]+)(?::|=)?(.*)?', part)
        if not m:
            continue

        qualifier, tag, value = m.groups()

        # 'all' tag uses qualifier
        if tag.lower() == "all":
            result[tag] = qualifier or "+"
            continue

        # Determine what to store
        value_to_store = value if value else None

        # Merge multiple occurrences into list
        if tag in result:
            existing = result[tag]
            if isinstance(existing, list):
                existing.append(value_to_store)
            else:
                result[tag] = [existing, value_to_store]
        else:
            result[tag] = value_to_store

    return result
def validate_dkim(dkim_string: str) -> bool:
    """Validate DKIM record syntax."""
    if not dkim_string:
        return False
    parts = [p.strip() for p in dkim_string.split(';') if p.strip()]
    tag_value_pattern = re.compile(r'^[a-zA-Z0-9]+=[^;]*$')
    tags_found = {}
    for part in parts:
        if not tag_value_pattern.match(part):
            return False
        key, value = part.split('=', 1)
        if key in tags_found:
            return False
        tags_found[key] = value
    if tags_found.get('v') != 'DKIM1':
        return False
    if 'p' not in tags_found:
        return False
    return True

def parse_dkim(dkim_string: str) -> dict:
    """Parse DKIM record and flag syntax errors."""
    if validate_dkim(dkim_string):
        result = dict(re.findall(r'(\w+)\s*=\s*([^;]+)', dkim_string))
        result["raw"] = dkim_string
        result["syntaxError"] = False
        return result
    return {"syntaxError": True, "raw": dkim_string}

# -------------------- DNS RECORDS --------------------

def get_A(domain: str) -> Optional[str]:
    if not validate_domain(domain):
        return None
    try:
        answers = resolver.resolve(domain, "A")
        return str(answers[0].address)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        return None
    except Exception as e:
        print(f"A record error for {domain}: {e}")
        return None

def get_SPF(domain: str) -> List[dict]:
    if not validate_domain(domain):
        return []
    results = []
    try:
        answers = resolver.resolve(domain, "TXT")
        for answer in answers:
            for txt in answer.strings:
                txt = txt.decode('utf-8', errors='ignore')
                if txt.startswith("v=spf1"):
                    results.append(parse_spf(txt))
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        pass
    return results

def get_DMARC(domain: str) -> List[dict]:
    if not validate_domain(domain):
        return []
    results = []
    try:
        answers = resolver.resolve(f"_dmarc.{domain}", "TXT")
        for answer in answers:
            for txt in answer.strings:
                txt = txt.decode('utf-8', errors='ignore')
                if txt.startswith("v=DMARC1"):
                    results.append(parse_dmarc(txt))
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        pass
    return results

def try_get_DKIM(domain: str) -> Optional[str]:
    try:
        answers = resolver.resolve(domain, "TXT")
        for txt_answer in answers:
            for txt in txt_answer.strings:
                txt = txt.decode("utf-8", errors="ignore")
                if 'v=' in txt or 'p=' in txt:
                    return txt
        # CNAME fallback
        try:
            cname_answers = resolver.resolve(domain, "CNAME")
            for ans in cname_answers:
                target = ans.target.to_text().rstrip('.')
                txt_answers = resolver.resolve(target, "TXT")
                for txt_answer in txt_answers:
                    for txt in txt_answer.strings:
                        txt = txt.decode("utf-8", errors="ignore")
                        if 'v=' in txt or 'p=' in txt:
                            return txt
        except dns.resolver.NoAnswer:
            pass
    except (dns.resolver.NXDOMAIN, dns.exception.Timeout):
        pass
    return None

def get_DKIM(domain: str) -> Dict[str, dict]:
    if not validate_domain(domain):
        return {}
    results = {"results": []}
    for selector in dkim_selectors:
        txt = try_get_DKIM(f"{selector}._domainkey.{domain}")
        if txt:
            results["results"].append({**{"selector": selector}, **parse_dkim(txt)})
    return results

# -------------------- SPF LOOKUPS --------------------

def count_lookups(domain: str, visited: Optional[Set[str]] = None) -> int:
    if visited is None:
        visited = set()
    if domain in visited:
        return 0
    visited.add(domain)
    spf_records = get_SPF(domain)
    count = 0
    for spf in spf_records:
        raw_spf = spf.get("raw", "")
        for part in raw_spf.split():
            p = part.lower()
            if p.startswith("include:"):
                count += 1 + count_lookups(p.split(":",1)[1], visited)
            elif p.startswith("redirect="):
                count += 1 + count_lookups(p.split("=",1)[1], visited)
            elif p in ["a","mx","ptr"] or any(p.startswith(x) for x in ["a:","mx:","ptr:","a/","mx/"]):
                count += 1
            elif p.startswith("exists:"):
                count += 1
            if count > MAX_LOOKUPS:
                return count
    return min(count, MAX_LOOKUPS+1)

# -------------------- DOMAIN ANALYSIS --------------------

def analyze_domain_records(domain: str) -> dict:
    if not validate_domain(domain):
        return {"warnings":[Codes.INVALID_DOMAIN.value], "spf":{"warnings":[]}, "dmarc":{"warnings":[]}, "dkim":{"warnings":[]}}
    
    spf = get_SPF(domain)
    dmarc = get_DMARC(domain)
    dkim = get_DKIM(domain)
    
    result = {"warnings":[],"spf":{"warnings":[]},"dmarc":{"warnings":[]},"dkim":{"warnings":[]}}
    
    # SPF warnings
    if not spf:
        result["spf"]["warnings"].append(Codes.RECORD_NOT_FOUND.value)
    elif len(spf) > 1:
        result["spf"]["warnings"].append(Codes.MULTIPLE_RECORDS_FOUND.value)
    
    # DMARC warnings
    if not dmarc:
        result["dmarc"]["warnings"].append(Codes.RECORD_NOT_FOUND.value)
    elif len(dmarc) > 1:
        result["dmarc"]["warnings"].append(Codes.MULTIPLE_RECORDS_FOUND.value)
    
    # DKIM warnings
    if not dkim.get("results"):
        result["dkim"]["warnings"].append(Codes.RECORD_NOT_FOUND.value)
    else:
        for r in dkim["results"]:
            r["warnings"] = []
            if r.get("syntaxError"):
                r["warnings"].append(Codes.RECORD_SYNTAX_ERROR.value)
    
    # Merge record values
    for s in spf: result["spf"].update(s)
    for d in dmarc: result["dmarc"].update(d)
    result["dkim"]["results"] = [{k:v for k,v in r.items() if k!="syntaxError"} for r in dkim.get("results",[])]
    
    # SPF lookup count
    try:
        lookups = count_lookups(domain)
        result["spf_lookup_count"] = lookups
        if lookups > MAX_LOOKUPS:
            result["spf"]["warnings"].append(Codes.LOOKUPS_LIMIT.value)
    except Exception as e:
        result["spf_lookup_count"] = None
        print(f"Error counting SPF lookups: {e}")
    
    # Domain not found if nothing exists
    if not spf and not dmarc and not dkim.get("results"):
        result["warnings"].append(Codes.DOMAIN_NOT_FOUND.value)
    
    return result

# -------------------- RDAP (OPTIONNEL) --------------------

def get_rdap_data(domain: str) -> dict:
    url = f"https://rdap.org/domain/{domain}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        print(f"RDAP error: {e}")
        return {}
