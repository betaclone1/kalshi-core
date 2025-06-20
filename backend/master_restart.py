import subprocess
import time
import signal
import psutil
import os
import sys

SCRIPTS = [
    "main.py",
    "api/coinbase-api/coinbase-btc/btc_price_watchdog.py",
    "api/kalshi-api/kalshi_api_watchdog.py",
]

processes = {}

def find_and_kill(script_name):
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(os.path.basename(s) == os.path.basename(script_name) for s in cmdline):
                print(f"Killing existing process PID {proc.pid} for {script_name}")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def kill_existing_scripts():
    for script in SCRIPTS:
        find_and_kill(script)
    # Wait for processes to exit
    timeout = 3
    interval = 0.5
    waited = 0
    while waited < timeout:
        still_running = False
        for script in SCRIPTS:
            for proc in psutil.process_iter(['cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and any(os.path.basename(s) == os.path.basename(script) for s in cmdline):
                        still_running = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        if not still_running:
            break
        time.sleep(interval)
        waited += interval
    if still_running:
        print("Warning: Some processes did not terminate after kill attempt.")

def start_scripts():
    global processes
    processes = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for script in SCRIPTS:
        try:
            log_out = open(f"{base_dir}/{os.path.basename(script)}.out.log", "a")
            log_err = open(f"{base_dir}/{os.path.basename(script)}.err.log", "a")
            print(f"Starting {script}")
            p = subprocess.Popen(
                [sys.executable, script],
                cwd=base_dir,
                stdout=log_out,
                stderr=log_err,
            )
            print(f"Started {script} with PID {p.pid}")
            processes[script] = (p, log_out, log_err)
        except Exception as e:
            print(f"Failed to start {script}: {e}")

def stop_script(script):
    global processes
    if script in processes:
        p, log_out, log_err = processes[script]
        print(f"Terminating PID {p.pid} ({script})")
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"PID {p.pid} did not terminate; killing")
            p.kill()
        log_out.close()
        log_err.close()
        del processes[script]

def stop_scripts():
    global processes
    for script in list(processes.keys()):
        stop_script(script)

def monitor_and_restart():
    print("Starting all scripts and monitoring for failures...")
    kill_existing_scripts()
    start_scripts()

    try:
        while True:
            time.sleep(5)  # Check every 5 seconds
            for script, (p, _, _) in list(processes.items()):
                retcode = p.poll()
                if retcode is not None:
                    print(f"{script} (PID {p.pid}) exited with code {retcode}. Restarting this script...")
                    stop_script(script)
                    # Restart only the failed script
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    try:
                        log_out = open(f"{base_dir}/{os.path.basename(script)}.out.log", "a")
                        log_err = open(f"{base_dir}/{os.path.basename(script)}.err.log", "a")
                        p_new = subprocess.Popen(
                            [sys.executable, script],
                            cwd=base_dir,
                            stdout=log_out,
                            stderr=log_err,
                        )
                        print(f"Restarted {script} with PID {p_new.pid}")
                        processes[script] = (p_new, log_out, log_err)
                    except Exception as e:
                        print(f"Failed to restart {script}: {e}")
    except KeyboardInterrupt:
        print("Stopping all scripts due to KeyboardInterrupt...")
        stop_scripts()
        print("Exited cleanly.")

if __name__ == "__main__":
    monitor_and_restart()
