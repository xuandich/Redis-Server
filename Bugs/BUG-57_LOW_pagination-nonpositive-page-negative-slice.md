# BUG-57: get_jobs_by_state: page không dương cho ra cửa sổ kết quả sai/rỗng do slicing âm

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-23

## Problem

Tham số query `page` được convert bằng `int()` nhưng không bao giờ được validate `>= 1`. Với `page=0` hoặc page âm, chỉ số slice tính ra âm và list slicing của Python lặng lẽ trả về cửa sổ ngoài ý muốn (hoặc rỗng) thay vì báo lỗi, trong khi `total_pages` và `page` trong response báo giá trị vô nghĩa.

## Root Cause

Trong [app.py](Dashboard/app.py#L78-L199):

```python
page = int(request.args.get('page', 1))   # dòng 78, không clamp >= 1
...
start = (page - 1) * per_page              # dòng 191
end = start + per_page                      # dòng 192
return ... all_jobs[start:end]              # dòng 195
```

Với `page=0`: `start=-20, end=0` → `all_jobs[-20:0]` cho `[]` (lặng lẽ giấu dữ liệu). Với `page=-1`: `start=-40, end=-20` → trả về 20 phần tử SAI đếm từ cuối list. Không có clamp page về `>= 1`.

## Scenario

Một caller (hoặc UI lỗi) gọi `/api/jobs_by_state?state=finished&page=0`. Thay vì lỗi rõ ràng, API trả về danh sách rỗng, khiến UI tưởng không có job nào.

## Impact

Caller truyền `page=0`/âm nhận về trang rỗng hoặc bị dịch chuyển một cách khó hiểu thay vì lỗi rõ, và UI phân trang có thể trông như mất job. Không crash, nhưng là lỗi đúng đắn ngầm trong API JSON công khai.

## Fix

Sau khi parse, clamp về `>= 1`:

```python
try:
    page = max(1, int(request.args.get('page', 1)))
except (TypeError, ValueError):
    return jsonify({'success': False, 'error': 'page phải là số nguyên'}), 400
```

Điều này đảm bảo `start = (page - 1) * per_page >= 0`.

## Related

Liên quan int-page-crashes-500 đã ghi nhận (nhánh non-int crash) — bug này bù phần page=0/âm chưa được xử lý; fix nên gộp cả clamp `>=1` lẫn try/except trả 400.
