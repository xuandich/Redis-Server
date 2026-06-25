# BUG-54: Dockerfile orchestrator bỏ qua requirements.txt và cài redis/rq/docker không pin, nguy cơ lệch version RQ với Dashboard

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-23

## Problem

Image orchestrator được build bằng `RUN pip install --no-cache-dir redis rq docker` (không pin version) và chỉ COPY `config.py main.py orchestrator.py`. Nó không bao giờ COPY hay cài `redis_server/requirements.txt`. Trong khi đó image Dashboard (build từ `./Dashboard`) là bên enqueue và dùng phiên bản redis/rq riêng. Hai image build độc lập, cả hai dùng version không pin (hoặc pin khác nhau).

## Root Cause

Trong [Dockerfile](redis_server/Dockerfile#L5-L7):

```dockerfile
RUN pip install --no-cache-dir redis rq docker
...
COPY config.py main.py orchestrator.py ./   # requirements.txt không bao giờ được cài
```

`pip install redis rq docker` không pin sẽ kéo bản mới nhất tại thời điểm build. `redis_server/requirements.txt` (liệt kê `redis>=8.0.0`, `rq>=2.9.1`) là dead cho image này, và còn không chứa `docker`. Đối chiếu [Dockerfile Dashboard](Dashboard/Dockerfile#L6-L7) có `COPY requirements.txt .` + `pip install -r requirements.txt`, với `redis==5.0.0`, `rq>=1.15.1` — đặc tả phân kỳ, một phần không chặn trên. Dashboard enqueue `main.crawl_job` vào RQ còn orchestrator worker dequeue/execute; serialization job, layout registry và schema key Redis của RQ phải khớp giữa enqueuer và worker.

## Scenario

Image orchestrator được build lại sau vài tuần, kéo RQ major version mới. Image Dashboard build từ trước dùng RQ cũ. Hai bên giờ lệch major version: job enqueue bởi Dashboard không deserialize được ở orchestrator worker, hoặc registry/status key bị đọc sai — mà không có thay đổi code nào, chỉ là rebuild.

## Impact

Vỡ thực thi job lặng lẽ sau khi rebuild image: lệch major version RQ giữa Dashboard enqueuer và orchestrator worker có thể khiến job fail deserialize, registry đọc sai, hoặc status key không khớp. Cũng làm build không reproducible.

## Fix

COPY `redis_server/requirements.txt` vào image và `pip install -r requirements.txt`, thêm `docker` và pin version khớp với Dashboard:

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

Và trong `requirements.txt`:

```
redis>=8.0.0,<9
rq>=2.9.1,<3
docker>=7.0.0,<8
```

Pin image Dashboard về cùng version để enqueuer và worker đồng bộ.

## Related

Liên quan start-sh-no-rebuild-on-code-change và docker-client-timeout-fixed-to-default đã ghi nhận ở tầng hạ tầng, nhưng đây là lỗi version skew RQ riêng biệt từ dependency không pin.
