# BUG-89_MEDIUM_orchestra-success-gate-has-no-product-path-marker-and-relies-on-a-generic-`h1`-s

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

orchestra success gate has no product-path marker and relies on a generic `h1` selector — …

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:169 and 175-176 (validation); 278-279, 319, 325 (success gate)

**Description**:
orchestra `_validate_product_page` (extractor.py:161-187) is the only positive gate the BUG-70 fix added. It accepts the page if:
1. URL still contains `shop-orchestra.com` or `orchestra.fr` (extractor.py:169), and
2. `p…

**Why Real**:
Read the actual current code: orchestra's only product check is domain-substring + a selector list whose first alternative is the near-universal `h1`. There is no path marker (unli…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: Orchestra's _validate_product_page function (extractor.py:161-187) validates product pages using: (1) domain substring match ('shop-orchestra.com' or 'orchestra.fr' in URL at line 169), and (2) CSS selector presence (h1, .product-name, etc. at lines 174-178). Unlike manomano (which checks for '/p/' path segment at extractor.py:190), orchestra has NO path-based marker validation. Real orchestra pro

## Impact

- Domain: false-success
- Source: P4
