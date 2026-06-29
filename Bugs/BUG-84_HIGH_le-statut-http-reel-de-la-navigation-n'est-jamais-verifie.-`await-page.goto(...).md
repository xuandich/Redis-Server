# BUG-84_HIGH_le-statut-http-reel-de-la-navigation-n'est-jamais-verifie.-`await-page.goto(...)

**Severity**: HIGH  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

Le statut HTTP reel de la navigation n'est JAMAIS verifie. `await page.goto(...)` (ligne 1…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:197,325 (goto response discarded; mark_success hardcodes http_code=200)

**Description**:
Le statut HTTP reel de la navigation n'est JAMAIS verifie. `await page.goto(...)` (ligne 197) renvoie un objet response mais sa valeur de retour n'est meme pas capturee ; `.status` n'est lu nulle part. A la reussite, `re…

**Why Real**:
Fausse reussite (false-success) : une page d'erreur serveur (HTTP 404/403/500 'produit introuvable', maintenance, soft-error) renvoyee avec un corps HTML contenant un <h1> et heber…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: high  
**reason**: The orchestra worker's navigation in _navigate_via_referer() (line 197) calls page.goto() but does NOT capture the returned Response object. Consequently, the HTTP status code is never read. The fetch_url() method then unconditionally calls mark_success() with hardcoded http_code=200 (line 325), regardless of actual server response status. This causes false-success: a server error page (HTTP 404/4

## Impact

- Domain: orchestra
- Source: P6
