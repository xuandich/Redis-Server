# BUG-86_MEDIUM_les-headers-stockes-dans-le-resultat-proviennent-du-listener-on_response-:-`if-'

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

Les headers stockes dans le resultat proviennent du listener on_response : `if 'orchestra'…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:224-228 (on_response capture des headers)

**Description**:
Les headers stockes dans le resultat proviennent du listener on_response : `if 'orchestra' in response.url and response.status == 200: response_headers.update(dict(response.headers))`. Deux problemes : (1) filtre par sou…

**Why Real**:
Le champ 'headers' du resultat n'est pas fiable : il peut refleter les headers d'une image/CSS/JS plutot que ceux de la page produit. Si aucune reponse ne matche (ex: domaine sans …

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: The headers field in orchestra crawl results is unreliable because it's populated by the on_response listener (workers/orchestra/sourceCode/extractor.py:224-226) which captures the LAST HTTP 200 response matching the filter `'orchestra' in response.url and response.status == 200`. This is problematic because:

1. **Filter matches multiple response types**: During page load, multiple HTTP 200 respo

## Impact

- Domain: orchestra
- Source: P6
