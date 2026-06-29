# BUG-87_MEDIUM_a-chaque-tentative,-le-proxy-est-choisi-par-`random.choice(self.proxies)`-(ligne

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

A chaque tentative, le proxy est choisi par `random.choice(self.proxies)` (ligne 288). Sur…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:288 (random.choice par tentative)

**Description**:
A chaque tentative, le proxy est choisi par `random.choice(self.proxies)` (ligne 288). Sur block CF / render_timeout / invalid_content, les logs disent 'doi proxy moi' (= changer pour un nouveau proxy, lignes 308,312,316…

**Why Real**:
Les 3 tentatives (max_retries=3) peuvent toutes utiliser le meme proxy bloque, epuisant le budget de retry sans reellement changer d'IP. Reduit l'efficacite du contournement anti-b…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: At line 288 of workers/orchestra/sourceCode/extractor.py, the proxy is selected via `random.choice(self.proxies)` on every retry attempt within the max_retries=3 loop. This means: (1) all 3 attempts can theoretically use the same blocked proxy; (2) on CF block, render_timeout, or invalid_content (lines 308, 312, 316, 320), the code logs "đổi proxy mới" (change to new proxy) but actually just calls

## Impact

- Domain: orchestra
- Source: P6
