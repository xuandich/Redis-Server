import threading
import time
from collections import deque
from datetime import datetime
import psutil
from rich.console import Console
from rich.table import Table
from typing import Dict


class DisplayManager:
    """Quản lý hiển thị với Rich - hiển thị 15 dòng log mới nhất + ETA"""
    def __init__(self):
        self.workers = {}
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.console = Console()
        self.log_buffer = deque(maxlen=100)
        self.worker_start_times = {}
        self.avg_request_times = {}
        
    def register_worker(self, worker_id: int, total_keys: int):
        with self.lock:
            self.workers[worker_id] = {
                'current': 0,
                'total': total_keys,
                'success': 0,
                'failed': 0,
                'current_product': 'Đang khởi động...',
                'price': '---',
                'name': 'Đang xử lý...',
                'status': '🟡 Init',
                'eta': 'Tính toán...',
                'proxy': 'Chưa kết nối',
                'proxy_country': '---'
            }
            self.worker_start_times[worker_id] = time.time()
            self.avg_request_times[worker_id] = 7.5
        self.refresh_display()
    
    def update_worker(self, worker_id: int, **kwargs):
        with self.lock:
            if worker_id in self.workers:
                for key, value in kwargs.items():
                    if key in self.workers[worker_id]:
                        self.workers[worker_id][key] = value
                
                w = self.workers[worker_id]
                if w['current'] > 0 and w['total'] > 0:
                    elapsed = time.time() - self.worker_start_times[worker_id]
                    avg_time_per_item = elapsed / w['current']
                    remaining_items = w['total'] - w['current']
                    eta_seconds = remaining_items * avg_time_per_item
                    
                    if eta_seconds < 60:
                        w['eta'] = f"{eta_seconds:.0f} giây"
                    elif eta_seconds < 3600:
                        w['eta'] = f"{eta_seconds/60:.1f} phút"
                    else:
                        w['eta'] = f"{eta_seconds/3600:.1f} giờ"
                    
                    self.avg_request_times[worker_id] = avg_time_per_item
        self.refresh_display()
    
    def update_avg_time(self, worker_id: int, request_time: float):
        with self.lock:
            if worker_id in self.avg_request_times:
                old_avg = self.avg_request_times[worker_id]
                new_avg = old_avg * 0.7 + request_time * 0.3
                self.avg_request_times[worker_id] = new_avg
    
    def get_status_icon(self, worker_data: Dict) -> str:
        if worker_data['status'] == '✅ Done':
            return "✅"
        elif worker_data['status'] == '❌ Error':
            return "❌"
        elif worker_data['current'] == 0:
            return "🟡"
        elif worker_data['current'] == worker_data['total']:
            return "✅"
        else:
            return "🟢"
    
    def add_log(self, worker_id: int, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] W{worker_id}: {message}"
        self.log_buffer.append(log_msg)
        self.refresh_display()
    
    def refresh_display(self):
        with self.lock:
            self.console.clear()
            
            elapsed = time.time() - self.start_time
            
            self.console.print(f"\n[bold cyan]🎯 FNAC EXTRACTOR - LIVE DASHBOARD[/bold cyan]")
            self.console.print(f"[yellow]⏱️  Thời gian chạy: {elapsed/60:.1f} phút[/yellow]")
            self.console.print()
            
            if not self.workers:
                self.console.print("[yellow]Đang khởi động workers...[/yellow]")
                return
            
            table = Table(title="📊 Worker Statistics", title_style="bold green", border_style="blue")
            table.add_column("Worker", style="cyan", width=10)
            table.add_column("Tiến độ", style="yellow", width=18)
            table.add_column("Kết quả", style="magenta", width=15)
            table.add_column("Proxy / Quốc gia", style="white", width=22)
            table.add_column("ETA", style="red", width=15)
            table.add_column("Sản phẩm", style="blue", width=27)
            table.add_column("Giá", style="green", width=10)
            table.add_column("Tên sản phẩm", style="cyan", width=35)
            
            for wid in sorted(self.workers.keys()):
                w = self.workers[wid]
                
                icon = self.get_status_icon(w)
                progress = f"{w['current']}/{w['total']} ({w['current']*100//w['total'] if w['total']>0 else 0}%)"
                results = f"✅{w['success']} ❌{w['failed']}"
                eta = w.get('eta', 'Tính toán...')
                
                if w['current'] > 0:
                    elapsed_worker = time.time() - self.worker_start_times.get(wid, time.time())
                    speed = w['current'] / (elapsed_worker / 60) if elapsed_worker > 0 else 0
                    speed_text = f"⚡{speed:.1f}spm"
                else:
                    speed_text = "⚡0spm"
                
                eta_display = f"{eta}\n{speed_text}"
                
                # Proxy & country info
                proxy_raw = w.get('proxy', 'Chưa kết nối')
                proxy_country = w.get('proxy_country', '---')
                if len(proxy_raw) > 18:
                    proxy_raw = proxy_raw[:15] + "..."
                proxy_display = f"{proxy_raw}\n🌍 {proxy_country}"
                
                product = w['current_product']
                if len(product) > 24:
                    product = product[:21] + "..."
                
                price_display = w.get('price', '---')
                name_display = w.get('name', 'Đang xử lý...')
                if len(name_display) > 32:
                    name_display = name_display[:29] + "..."
                
                table.add_row(
                    f"{icon} W{wid}", 
                    progress, 
                    results, 
                    proxy_display,
                    eta_display,
                    product, 
                    price_display, 
                    name_display
                )
            
            self.console.print(table)
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            
            total_remaining = 0
            for wid in self.workers:
                w = self.workers[wid]
                remaining = w['total'] - w['current']
                if remaining > 0 and w['current'] > 0:
                    elapsed_worker = time.time() - self.worker_start_times.get(wid, time.time())
                    avg = elapsed_worker / w['current']
                    remaining_time = remaining * avg
                    if remaining_time > total_remaining:
                        total_remaining = remaining_time
            
            if total_remaining > 0:
                if total_remaining < 60:
                    total_eta = f"{total_remaining:.0f} giây"
                elif total_remaining < 3600:
                    total_eta = f"{total_remaining/60:.1f} phút"
                else:
                    total_eta = f"{total_remaining/3600:.1f} giờ"
            else:
                total_eta = "Đang tính..."
            
            self.console.print(f"\n[white]💻 CPU: {cpu_percent:.0f}% | RAM: {ram.used/1024/1024/1024:.1f}GB/{ram.total/1024/1024/1024:.1f}GB ({ram.percent:.0f}%)[/white]")
            
            total_success = sum(w['success'] for w in self.workers.values())
            total_failed = sum(w['failed'] for w in self.workers.values())
            total_processed = total_success + total_failed
            total_all = sum(w['total'] for w in self.workers.values())
            total_rate = f"{(total_success/total_processed*100):.1f}%" if total_processed > 0 else "0%"
            
            self.console.print(f"[bold yellow]📊 TOTAL: [/bold yellow][green]✅{total_success}[/green] [red]❌{total_failed}[/red] [white]| {total_processed}/{total_all} | {total_rate} | ETA còn lại: {total_eta}[/white]")
            
            self.console.print(f"\n[bold cyan]📝 LOGS (15 dòng mới nhất)[/bold cyan]")
            self.console.print("-" * 100, style="dim")
            
            if self.log_buffer:
                log_list = list(self.log_buffer)
                for log in log_list[-15:]:
                    self.console.print(f"  {log}", style="dim")
            else:
                self.console.print("  Chưa có log nào...", style="dim")
    
    def stop(self):
        self.refresh_display()
        self.console.print("\n[bold green]✅ KẾT THÚC CHƯƠNG TRÌNH[/bold green]")