"""
Job Results Dashboard - Track jobs từ Redis result:{ret_key} keys
Phù hợp với test_batch.py / test_job.py / main.py
"""
import os
import json
import logging
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
    valid_states = ['queued', 'started', 'running', 'finished', 'failed']
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
    valid_states = ['queued', 'started', 'running', 'finished', 'failed']
    if state not in valid_states:
        return jsonify({'error': 'Invalid state'}), 400

    page = int(request.args.get('page', 1))
    per_page = 20
    all_jobs = []

    try:
        if state in ['queued', 'started', 'running']:
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

            # For queued: also scan actual RQ queues (jobs not yet picked up may lack job_state)
            if state == 'queued':
                queue_keys = redis_conn.keys('rq:queue:*')
                for k in queue_keys:
                    if isinstance(k, bytes):
                        k = k.decode()
                    queue_name = k.replace('rq:queue:', '')
                    try:
                        q = Queue(queue_name, connection=redis_conn)
                        for job_id in q.get_job_ids():
                            try:
                                job = Job.fetch(job_id, connection=redis_conn)
                                ret_key = job.kwargs.get('ret_key', job_id)
                                if ret_key not in seen:
                                    seen.add(ret_key)
                                    all_jobs.append({
                                        'ret_key': ret_key,
                                        'url': job.kwargs.get('url', 'N/A'),
                                        'domain': job.kwargs.get('domain', 'unknown'),
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
                            all_jobs.append({
                                'ret_key': ret_key,
                                'url': result.get('url', 'N/A'),
                                'domain': result.get('domain', 'unknown'),
                                'status': job_status,
                                'http_code': result.get('http_code', 0),
                                'error': result.get('error', ''),
                                'total_elapsed_seconds': result.get('total_elapsed_seconds', 0),
                                'html_size': len(result.get('html', '')),
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
        'started': [],
        'running': [],
        'finished': [],
        'failed': []
    }

    try:
        # Scan RQ queues for queued jobs (auto-discover from Redis)
        try:
            queue_keys = redis_conn.keys('rq:queue:*') + redis_conn.keys('crawler:*')
            queue_names = set()
            for k in queue_keys:
                if isinstance(k, bytes):
                    k = k.decode()
                if k.startswith('rq:queue:'):
                    queue_names.add(k.replace('rq:queue:', ''))
                elif ':' in k and not k.startswith('rq:') and not k.startswith('job_state:') and not k.startswith('result:') and not k.startswith('slots:'):
                    queue_names.add(k)
            for queue_name in queue_names:
                try:
                    q = Queue(queue_name, connection=redis_conn)
                    for job_id in q.get_job_ids():
                        try:
                            job = Job.fetch(job_id, connection=redis_conn)
                            # Extract ret_key from kwargs
                            ret_key = job.kwargs.get('ret_key', job_id)
                            url = job.kwargs.get('url', 'N/A')
                            domain = job.kwargs.get('domain', 'unknown')

                            job_info = {
                                'ret_key': ret_key[:8],
                                'ret_key_full': ret_key,
                                'url': url,
                                'domain': domain,
                                'status': 'queued',
                            }
                            jobs_data['queued'].append(job_info)
                        except:
                            pass
                except:
                    pass
        except:
            pass

        # Scan job_state:* keys (queued/started/running jobs)
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
                    state = state_data.get('state', 'unknown')

                    job_info = {
                        'ret_key': ret_key[:8],
                        'ret_key_full': ret_key,
                        'url': state_data.get('url', 'N/A'),
                        'domain': state_data.get('domain', 'unknown'),
                        'status': state,
                    }

                    # Categorize by state
                    if state == 'queued':
                        jobs_data['queued'].append(job_info)
                    elif state == 'started':
                        jobs_data['started'].append(job_info)
                    elif state == 'running':
                        jobs_data['running'].append(job_info)
                except:
                    pass
            if cursor == 0:
                break

        # Scan result:* keys (finished/failed jobs)
        cursor = 0
        result_keys = []
        while True:
            cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
            result_keys.extend(keys)
            if cursor == 0:
                break

        logger.info(f"Found {len(result_keys)} result keys, queued={len(jobs_data['queued'])}, started={len(jobs_data['started'])}")

        # Parse mỗi result
        for key in result_keys:
            try:
                value = redis_conn.get(key)
                if not value:
                    continue

                result = json.loads(value)
                ret_key = key.replace('result:', '')

                job_info = {
                    'ret_key': ret_key[:8],
                    'ret_key_full': ret_key,
                    'url': result.get('url', 'N/A'),
                    'domain': result.get('domain', 'unknown'),
                    'status': result.get('status', 'unknown'),
                    'http_code': result.get('http_code', 0),
                    'error': result.get('error', ''),
                    'html_size': len(result.get('html', '')),
                    'total_elapsed_seconds': result.get('total_elapsed_seconds', 0),
                }

                # Categorize by status
                if result.get('status') == 'success':
                    jobs_data['finished'].append(job_info)
                else:
                    jobs_data['failed'].append(job_info)

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from {key}")
                continue
            except Exception as e:
                logger.error(f"Error processing {key}: {e}")
                continue

        # Sort by ret_key (most recent last)
        for status in ['queued', 'started', 'finished', 'failed']:
            jobs_data[status].sort(key=lambda x: x['ret_key_full'], reverse=True)

        logger.info(f"Returning: Queued={len(jobs_data['queued'])}, "
                   f"Started={len(jobs_data['started'])}, "
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
    """Clear all jobs in a specific state (queued, started, running)"""
    logger.info(f"Clearing {state} jobs...")

    if state not in ['queued', 'started', 'running', 'finished']:
        return jsonify({'error': 'Invalid state'}), 400

    try:
        deleted_count = 0

        if state == 'queued':
            # Clear actual RQ queues
            raw_keys = redis_conn.smembers('rq:queues') or set()
            queue_names = {k.replace('rq:queue:', '', 1) for k in raw_keys}
            for queue_name in queue_names:
                try:
                    q = Queue(queue_name, connection=redis_conn)
                    count = len(q.get_job_ids())
                    q.empty()
                    deleted_count += count
                    logger.info(f"Emptied queue {queue_name}: {count} jobs")
                except Exception as e:
                    logger.warning(f"Error clearing queue {queue_name}: {e}")
            # Also clear job_state:* keys with state='queued'
            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor, match='job_state:*', count=100)
                for key in keys:
                    try:
                        value = redis_conn.get(key)
                        if value and json.loads(value).get('state') == 'queued':
                            redis_conn.delete(key)
                            deleted_count += 1
                    except:
                        pass
                if cursor == 0:
                    break
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
        else:
            # Clear from job_state:* keys
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
