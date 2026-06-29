# BUG-85_MEDIUM_apres-'cf-pass',-le-code-attend-le-rendu-via-page.wait_for_function('document.bo

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

Apres 'CF pass', le code attend le rendu via page.wait_for_function('document.body && docu…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:263 (except TimeoutError sur wait_for_function)

**Description**:
Apres 'CF pass', le code attend le rendu via page.wait_for_function('document.body && document.body.innerHTML.length > 5000', timeout=20000) puis `except TimeoutError:` (ligne 263) renvoie status='render_timeout'. Mais w…

**Why Real**:
La semantique voulue 'rendu incomplet -> retry avec nouveau proxy' est perdue. Une page qui n'atteint jamais 5000 octets de body dans les 20s (rendu partiel, page legere d'erreur) …

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: After CloudFlare pass (lines 257-266 in workers/orchestra/sourceCode/extractor.py and workers/manomano/sourceCode/extractor.py), the code awaits `page.wait_for_function('document.body && document.body.innerHTML.length > 5000', timeout=20000)`. When this times out (TimeoutError caught at line 263/278), it returns status='render_timeout' and immediately exits—skipping the validation layer at line 27

## Impact

- Domain: orchestra
- Source: P6
