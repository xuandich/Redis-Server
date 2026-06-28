"""
Job Results Dashboard - Track jobs từ Redis result:{ret_key} keys
Phù hợp với test_batch.py / test_job.py / main.py
"""
import os
import json
import logging
import uuid
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from redis import Redis
from rq import Queue, Worker
from rq.job import Job
from dotenv import load_dotenv

load_dotenv()

# Logging
if not os.path.exists('logs'):
    os.makedirs('logs')

handler = RotatingFileHandler(
    'logs/dashboard.log',
    maxBytes=10*1024*1024,
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Redis connection
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_db = int(os.getenv('REDIS_DB', 0))

redis_conn = Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

logger.info(f"Connected to Redis: {redis_host}:{redis_port}/{redis_db}")
logger.info("Tracking job results from result:* keys")


@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/jobs/<state>')
def jobs_list(state):
    """Paginated job list page for a specific state"""
    valid_states = ['queued', 'running', 'finished', 'failed']
    if state not in valid_states:
        return "Invalid state", 404
    return render_template('jobs_list.html', state=state)


@app.route('/job/<ret_key>')
def job_detail(ret_key):
    """Job detail page"""
    return render_template('job_detail.html', ret_key=ret_key)


@app.route('/api/jobs/<state>')
def get_jobs_by_state(state):
    """Paginated API for jobs in a specific state"""
    valid_states = ['queued', 'running', 'finished', 'failed']
    if state not in valid_states:
        return jsonify({'error': 'Invalid state'}), 400

    page = int(request.args.get('page', 1))
    per_page = 20
    all_jobs = []

    try:
        if state in ['queued', 'running']:
            # Scan job_state:* keys (set by test_batch.py and main.py)
            seen = set()
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='job_state:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if not value:
                            continue
                        data = json.loads(value)
                        if data.get('state') == state:
                            ret_key = data.get('ret_key', '')
                            if ret_key not in seen:
                                seen.add(ret_key)
                                all_jobs.append({
                                    'ret_key': ret_key,
                                    'url': data.get('url', 'N/A'),
                                    'domain': data.get('domain', 'unknown'),
                                    'status': state,
                                    'timestamp': data.get('timestamp', 0),
                                })
                    except:
                        pass
                if cursor == 0:
                    break

            # For queued: also scan actual RQ queues - dùng pipeline batch fetch
            if state == 'queued':
                queue_keys = redis_conn.keys('rq:queue:crawler:*')
                for k in queue_keys:
                    if isinstance(k, bytes):
                        k = k.decode()
                    queue_name = k.replace('rq:queue:', '')
                    domain = queue_name.replace('crawler:', '')
                    try:
                        job_ids = redis_conn.lrange(k, 0, -1)
                        if not job_ids:
                            continue

                        # Batch fetch bằng pipeline
                        pipe = redis_conn.pipeline()
                        for job_id in job_ids:
                            if isinstance(job_id, bytes):
                                job_id = job_id.decode()
                            pipe.hgetall(f'rq:job:{job_id}')
                        job_hashes = pipe.execute()

                        for job_id, job_hash in zip(job_ids, job_hashes):
                            try:
                                if isinstance(job_id, bytes):
                                    job_id = job_id.decode()
                                if not job_hash:
                                    continue
                                ret_key = job_id  # job_id=ret_key trong hệ thống này
                                if ret_key not in seen:
                                    seen.add(ret_key)
                                    description = job_hash.get(b'description', b'').decode() if isinstance(job_hash.get(b'description', b''), bytes) else job_hash.get('description', '')
                                    url = 'N/A'
                                    import re
                                    match = re.search(r"url='([^']+)'", description)
                                    if match:
                                        url = match.group(1)
                                    all_jobs.append({
                                        'ret_key': ret_key,
                                        'url': url,
                                        'domain': domain,
                                        'status': 'queued',
                                    })
                            except:
                                pass
                    except:
                        pass

        elif state in ['finished', 'failed']:
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if not value:
                            continue
                        result = json.loads(value)
                        job_status = result.get('status', 'unknown')
                        is_finished = (state == 'finished' and job_status == 'success')
                        is_failed = (state == 'failed' and job_status != 'success')
                        if is_finished or is_failed:
                            ret_key = key.replace('result:', '')
                            html = result.get('html') or ''
                            all_jobs.append({
                                'ret_key': ret_key,
                                'url': result.get('url', 'N/A'),
                                'domain': result.get('domain', 'unknown'),
                                'status': job_status,
                                'http_code': result.get('http_code', 0),
                                'error': result.get('error', ''),
                                'total_elapsed_seconds': result.get('total_elapsed_seconds', 0),
                                'html_size': len(html),
                                'timestamp': result.get('timestamp', 0),
                            })
                    except:
                        pass
                if cursor == 0:
                    break

        total = len(all_jobs)
        start = (page - 1) * per_page
        end = start + per_page

        return jsonify({
            'jobs': all_jobs[start:end],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': max(1, (total + per_page - 1) // per_page),
            'state': state,
        })

    except Exception as e:
        logger.error(f"Error fetching {state} jobs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/job_detail/<ret_key>')
def get_job_detail_api(ret_key):
    """Full detail of a single job"""
    try:
        value = redis_conn.get(f"result:{ret_key}")
        if value:
            return jsonify({'source': 'result', 'data': json.loads(value)})
        value = redis_conn.get(f"job_state:{ret_key}")
        if value:
            return jsonify({'source': 'job_state', 'data': json.loads(value)})
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs')
def get_jobs():
    """
    API lấy tất cả job results từ Redis result:* keys
    Grouped by status: success, failed, pending (trong processing)
    """
    logger.info("Fetching jobs from Redis result:* keys...")

    jobs_data = {
        'queued': [],
        'running': [],
        'finished': [],
        'failed': []
    }

    try:
        # Scan result:* keys TRƯỚC - parse ngay + build seen_result để tránh duplicate
        seen_result = set()
        cursor = 0
        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
            for key in keys:
                try:
                    ret_key = key.replace('result:', '')
                    if ret_key in seen_result:
                        continue  # SCAN trả duplicate khi Redis rehash
                    seen_result.add(ret_key)

                    value = redis_conn.get(key)
                    if not value:
                        continue
                    result = json.loads(value)

                    html = result.get('html') or ''
                    job_info = {
                        'ret_key': ret_key,
                        'url': result.get('url', 'N/A'),
                        'domain': result.get('domain', 'unknown'),
                        'status': result.get('status', 'unknown'),
                        'http_code': result.get('http_code', 0),
                        'error': result.get('error', ''),
                        'html_size': len(html),
                        'total_elapsed_seconds': result.get('total_elapsed_seconds', 0),
                        'timestamp': result.get('timestamp', 0),
                    }
                    if result.get('status') == 'success':
                        jobs_data['finished'].append(job_info)
                    else:
                        jobs_data['failed'].append(job_info)
                except:
                    pass
            if cursor == 0:
                break

        # Scan job_state:* keys - skip nếu đã có result (tránh đếm 2 lần)
        seen_queued = set()
        cursor = 0
        while True:
            cursor, state_keys = redis_conn.scan(cursor, match='job_state:*', count=100)
            for key in state_keys:
                try:
                    value = redis_conn.get(key)
                    if not value:
                        continue
                    state_data = json.loads(value)
                    ret_key = state_data.get('ret_key', '')
                    if ret_key in seen_result:
                        continue  # đã có result, bỏ qua job_state cũ
                    state = state_data.get('state', 'unknown')

                    job_info = {
                        'ret_key': ret_key,
                        'url': state_data.get('url', 'N/A'),
                        'domain': state_data.get('domain', 'unknown'),
                        'status': state,
                    }

                    if state == 'queued':
                        seen_queued.add(ret_key)
                        jobs_data['queued'].append(job_info)
                    elif state == 'running':
                        jobs_data['running'].append(job_info)
                except:
                    pass
            if cursor == 0:
                break

        # Scan RQ queues - bổ sung jobs chưa có job_state
        try:
            queue_keys = redis_conn.keys('rq:queue:crawler:*')
            for k in queue_keys:
                if isinstance(k, bytes):
                    k = k.decode()
                domain = k.replace('rq:queue:crawler:', '')
                try:
                    job_ids = redis_conn.lrange(k, 0, -1)
                    if not job_ids:
                        continue

                    pipe = redis_conn.pipeline()
                    for job_id in job_ids:
                        if isinstance(job_id, bytes):
                            job_id = job_id.decode()
                        pipe.hgetall(f'rq:job:{job_id}')
                    job_hashes = pipe.execute()

                    for job_id, job_hash in zip(job_ids, job_hashes):
                        try:
                            if isinstance(job_id, bytes):
                                job_id = job_id.decode()
                            if not job_hash:
                                continue
                            ret_key = job_id  # job_id=ret_key khi enqueue
                            if ret_key in seen_queued or ret_key in seen_result:
                                continue  # đã có từ job_state hoặc result
                            description = job_hash.get('description', '')
                            import re
                            url_match = re.search(r"url='([^']+)'", description)
                            url = url_match.group(1) if url_match else 'N/A'
                            jobs_data['queued'].append({
                                'ret_key': ret_key,
                                'url': url,
                                'domain': domain,
                                'status': 'queued',
                            })
                        except:
                            pass
                except:
                    pass
        except:
            pass

        logger.info(f"result={len(seen_result)}, queued={len(jobs_data['queued'])}, running={len(jobs_data['running'])}")

        # Sort by timestamp (newest first)
        for status in ['queued', 'running', 'finished', 'failed']:
            jobs_data[status].sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        logger.info(f"Returning: Queued={len(jobs_data['queued'])}, "
                   f"Running={len(jobs_data['running'])}, "
                   f"Finished={len(jobs_data['finished'])}, "
                   f"Failed={len(jobs_data['failed'])}")

        return jsonify(jobs_data)

    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """API lấy thống kê"""
    try:
        cursor = 0
        total_keys = 0
        success_count = 0
        failed_count = 0
        domain_counts = {}

        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)

            for key in keys:
                total_keys += 1
                try:
                    value = redis_conn.get(key)
                    if value:
                        result = json.loads(value)
                        status = result.get('status', 'unknown')
                        domain = result.get('domain', 'unknown')

                        if status == 'success':
                            success_count += 1
                        else:
                            failed_count += 1

                        domain_counts[domain] = domain_counts.get(domain, 0) + 1
                except:
                    pass

            if cursor == 0:
                break

        stats = {
            'total': total_keys,
            'success': success_count,
            'failed': failed_count,
            'success_rate': (success_count / total_keys * 100) if total_keys > 0 else 0,
            'by_domain': domain_counts
        }

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete/<ret_key>', methods=['POST'])
def delete_job(ret_key):
    """API xóa 1 job result"""
    logger.info(f"Deleting result: {ret_key}")

    try:
        key = f"result:{ret_key}"
        if redis_conn.exists(key):
            redis_conn.delete(key)
            logger.info(f"Deleted: {key}")
            return jsonify({'success': True, 'message': 'Job result deleted'})
        else:
            return jsonify({'error': 'Not found'}), 404

    except Exception as e:
        logger.error(f"Error deleting {ret_key}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear_finished', methods=['POST'])
def clear_finished():
    """API xóa tất cả finished/failed jobs"""
    logger.info("Clearing finished jobs...")

    try:
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)

            for key in keys:
                try:
                    value = redis_conn.get(key)
                    if value:
                        result = json.loads(value)
                        status = result.get('status', '')
                        # Delete success và failed (keep pending)
                        if status in ['success', 'failed']:
                            redis_conn.delete(key)
                            deleted_count += 1
                except:
                    pass

            if cursor == 0:
                break

        logger.info(f"Deleted {deleted_count} finished/failed jobs")
        return jsonify({'success': True, 'deleted': deleted_count})

    except Exception as e:
        logger.error(f"Error clearing finished: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/job/<ret_key>')
def get_job_detail(ret_key):
    """API lấy chi tiết 1 job"""
    try:
        key = f"result:{ret_key}"
        value = redis_conn.get(key)

        if not value:
            return jsonify({'error': 'Not found'}), 404

        result = json.loads(value)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching job {ret_key}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/workers')
def get_workers():
    """API lấy thông tin workers (compat with template)"""
    # Không dùng RQ workers, return empty list
    return jsonify([])


@app.route('/api/cancel/<ret_key>', methods=['POST'])
def cancel_job_compat(ret_key):
    """API cancel/delete job (compat with template)"""
    logger.info(f"Deleting result: {ret_key}")
    try:
        key = f"result:{ret_key}"
        if redis_conn.exists(key):
            redis_conn.delete(key)
            logger.info(f"Deleted: {key}")
            return jsonify({'success': True, 'message': 'Job result deleted'})
        else:
            return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting {ret_key}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear_queue', methods=['POST'])
def clear_queue_compat():
    """API clear queue (compat with template - same as clear_finished)"""
    logger.info("Clearing finished jobs...")
    try:
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
            for key in keys:
                try:
                    value = redis_conn.get(key)
                    if value:
                        result = json.loads(value)
                        status = result.get('status', '')
                        if status in ['success', 'failed']:
                            redis_conn.delete(key)
                            deleted_count += 1
                except:
                    pass
            if cursor == 0:
                break

        logger.info(f"Deleted {deleted_count} finished/failed jobs")
        return jsonify({'success': True, 'message': f'Đã xóa {deleted_count} jobs', 'deleted': deleted_count})

    except Exception as e:
        logger.error(f"Error clearing queue: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/queue_stats')
def queue_stats_compat():
    """API queue stats (compat with template)"""
    try:
        cursor = 0
        total_keys = 0
        success_count = 0
        failed_count = 0

        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
            for key in keys:
                total_keys += 1
                try:
                    value = redis_conn.get(key)
                    if value:
                        result = json.loads(value)
                        status = result.get('status', 'unknown')
                        if status == 'success':
                            success_count += 1
                        else:
                            failed_count += 1
                except:
                    pass
            if cursor == 0:
                break

        stats = {
            'total': total_keys,
            'success': success_count,
            'failed': failed_count,
            'success_rate': (success_count / total_keys * 100) if total_keys > 0 else 0,
        }
        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear_state/<state>', methods=['POST'])
def clear_state(state):
    """Clear all jobs in a specific state (queued, running, finished, failed)"""
    logger.info(f"Clearing {state} jobs...")

    if state not in ['queued', 'running', 'finished', 'failed']:
        return jsonify({'error': 'Invalid state'}), 400

    try:
        deleted_count = 0

        if state == 'queued':
            deleted_keys = set()
            # Clear actual RQ queues — track ret_keys removed
            for q in Queue.all(connection=redis_conn):
                try:
                    for jid in q.get_job_ids():
                        deleted_keys.add(jid)
                    q.empty()
                    logger.info(f"Emptied queue {q.name}: {len(deleted_keys)} jobs")
                except Exception as e:
                    logger.warning(f"Error clearing queue {q.name}: {e}")
            # Also clear job_state:* keys with state='queued'
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='job_state:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if value and json.loads(value).get('state') == 'queued':
                            redis_conn.delete(key)
                            deleted_keys.add(key.split('job_state:', 1)[-1])
                    except:
                        pass
                if cursor == 0:
                    break
            deleted_count = len(deleted_keys)
        elif state == 'finished':
            # Clear from result:* keys where status == success
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if value:
                            result = json.loads(value)
                            if result.get('status') == 'success':
                                redis_conn.delete(key)
                                deleted_count += 1
                    except:
                        pass
                if cursor == 0:
                    break
        elif state == 'failed':
            # Clear from result:* keys where status != success
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if value:
                            result = json.loads(value)
                            if result.get('status') != 'success':
                                redis_conn.delete(key)
                                deleted_count += 1
                    except:
                        pass
                if cursor == 0:
                    break
        else:
            # Clear from job_state:* keys (running)
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='job_state:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if value:
                            state_data = json.loads(value)
                            job_state = state_data.get('state', '')
                            if job_state == state:
                                redis_conn.delete(key)
                                deleted_count += 1
                    except:
                        pass
                if cursor == 0:
                    break

        logger.info(f"Deleted {deleted_count} {state} jobs")
        return jsonify({'success': True, 'deleted': deleted_count, 'message': f'Deleted {deleted_count} {state} jobs'})

    except Exception as e:
        logger.error(f"Error clearing {state} jobs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear_failed', methods=['POST'])
def clear_failed():
    """Clear all failed jobs from result:* keys"""
    logger.info("Clearing failed jobs...")

    try:
        cursor = 0
        deleted_count = 0

        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)

            for key in keys:
                try:
                    value = redis_conn.get(key)
                    if value:
                        result = json.loads(value)
                        status = result.get('status', '')
                        if status != 'success':  # Delete all non-success (failed, error, etc)
                            redis_conn.delete(key)
                            deleted_count += 1
                except:
                    pass

            if cursor == 0:
                break

        logger.info(f"Deleted {deleted_count} failed jobs")
        return jsonify({'success': True, 'deleted': deleted_count, 'message': f'Deleted {deleted_count} failed jobs'})

    except Exception as e:
        logger.error(f"Error clearing failed jobs: {e}")
        return jsonify({'error': str(e)}), 500


def _extract_domain_from_url(url: str) -> str:
    """Extract domain from URL (fnac, amazon, newark, etc.)"""
    from urllib.parse import urlparse
    try:
        netloc = urlparse(url).netloc.lower()
        if 'fnac' in netloc:
            return 'fnac'
        elif 'amazon' in netloc:
            return 'amazon'
        elif 'newark' in netloc:
            return 'newark'
        else:
            return netloc.split('.')[-2] if netloc.count('.') >= 1 else netloc.split('.')[0]
    except:
        return None


@app.route('/api/submit-job', methods=['POST'])
def submit_job():
    """
    API submit job từ external client (PHP server, etc.)

    Request body (JSON):
    {
      "url": "https://www.fnac.com/product",
      "mode": "none",
      "proxy_type": "standard",
      "ret_key": "client-generated-uuid"
    }

    Domain được extract từ URL để determine queue.

    Response:
    {
      "ret_key": "uuid",
      "status": "queued",
      "message": "Job enqueued successfully"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON body provided'}), 400

        url = data.get('url', '').strip()
        mode = data.get('mode', 'none').strip()
        proxy_type = data.get('proxy_type', 'standard').strip()
        ret_key = data.get('ret_key', '').strip()

        # Validate required fields
        if not url:
            return jsonify({'error': 'Missing required field: url'}), 400
        if not ret_key:
            return jsonify({'error': 'Missing required field: ret_key'}), 400

        # Extract domain from ret_key (format: ret_{domain}_{uuid})
        # Fallback to URL extraction if ret_key format doesn't match
        parts = ret_key.split('_', 2)
        if len(parts) >= 2 and parts[0] == 'ret':
            domain = parts[1]
        else:
            domain = _extract_domain_from_url(url)
        if not domain:
            return jsonify({'error': 'Cannot determine domain from ret_key or URL'}), 400

        # Validate proxy_type
        valid_proxy_types = ['standard', 'none']
        if proxy_type not in valid_proxy_types:
            return jsonify({'error': f'Invalid proxy_type. Must be one of: {", ".join(valid_proxy_types)}'}), 400

        # Enqueue to the appropriate domain queue (extracted from URL)
        try:
            import time as _time
            queue_name = f'crawler:{domain}'
            queue = Queue(queue_name, connection=redis_conn)

            # BUG-60: bảo toàn retry_count nếu job_state cũ còn tồn tại (re-submit cùng
            # ret_key). Ghi đè vô điều kiện sẽ reset cap retry của crash-recovery về 0,
            # khiến job luôn-lỗi bị re-enqueue vô hạn. Giống main.py:_set_job_state.
            retry_count = 0
            existing_state = redis_conn.get(f'job_state:{ret_key}')
            if existing_state:
                try:
                    retry_count = json.loads(existing_state).get('retry_count', 0)
                except Exception:
                    pass

            # Tạo job_state:* key để dashboard track được (giống test_batch.py)
            job_state_data = {
                'state': 'queued',
                'ret_key': ret_key,
                'url': url,
                'domain': domain,
                'proxy_type': proxy_type,
                'retry_count': retry_count,
                'timestamp': _time.time(),
            }
            redis_conn.set(f'job_state:{ret_key}', json.dumps(job_state_data), ex=86400)

            # Enqueue the job - RQ will call 'main.crawl_job'
            job = queue.enqueue(
                'main.crawl_job',
                url=url,
                domain=domain,
                ret_key=ret_key,
                proxy_type=proxy_type,
                job_timeout=int(os.getenv(f'JOB_TIMEOUT_{domain.upper()}', os.getenv('JOB_TIMEOUT_DEFAULT', 120))),
                job_id=ret_key
            )

            logger.info(f"[API] Job submitted: ret_key={ret_key[:8]}, domain={domain}, mode={mode}, url={url[:60]}...")

            return jsonify({
                'ret_key': ret_key,
                'ret_key_short': ret_key[:8],
                'status': 'queued',
                'message': 'Job enqueued successfully',
                'domain': domain,
                'mode': mode,
                'url': url
            }), 202

        except Exception as e:
            logger.error(f"[API] Error enqueuing job: {e}")
            try:
                redis_conn.delete(f'job_state:{ret_key}')
                error_result = {
                    'status': 'failed',
                    'error': f'Enqueue failed: {str(e)}',
                    'ret_key': ret_key,
                    'url': url,
                    'domain': domain,
                }
                redis_conn.set(f'result:{ret_key}', json.dumps(error_result), ex=3600)
            except Exception:
                pass
            return jsonify({'error': f'Failed to enqueue job: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"[API] Error in submit_job: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    host = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    port = int(os.getenv('DASHBOARD_PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    logger.info(f"Starting dashboard on {host}:{port} (debug={debug})")
    logger.info(f"Redis: {redis_host}:{redis_port}/{redis_db}")
    app.run(host=host, port=port, debug=debug)
