#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import subprocess
import time
import os

# ========== 配置区域 ==========

# 服务器列表
SERVERS = [
    "apt086.apt.emulab.net",
    "apt075.apt.emulab.net"
]
# 0 is the log

# SSH 私钥文件路径
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_ed25519")

# 需要上传的配置文件路径（本地）
LOCAL_FDB_CONF_PATH = "foundationdb.conf"
LOCAL_STORAGETYPE_JSON_PATH = "storagetype.json"

# 远端配置文件的路径
REMOTE_FDB_CONF_PATH = "/etc/foundationdb/foundationdb.conf"
REMOTE_STORAGETYPE_JSON_PATH = "/etc/foundationdb/storagetype.json"

# 在远端新建存储目录路径
REMOTE_DATA_BASEDIR = "/mydata"

# ========== 函数定义 ==========

def create_ssh_client(
    hostname: str,
    username: str = "gyming",
    key_filename: str = SSH_KEY_PATH,
    timeout: int = 10
) -> paramiko.SSHClient:
    """
    创建并返回一个 paramiko SSH client。
    需要你已经配置好公钥免密登录或者有其它安全处理方式。
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname,
        username=username,
        key_filename=key_filename,
        timeout=timeout
    )
    return client


def run_remote_command(ssh_client: paramiko.SSHClient, command: str) -> None:
    """
    在远程服务器上执行一条命令并打印输出。
    假设服务器已允许免密码 sudo；否则需要通过 stdin 写入密码。
    """
    print(f"[REMOTE CMD] {command}")
    stdin, stdout, stderr = ssh_client.exec_command(command)
    # 如果需要sudo密码，可使用 stdin.write('your_password\n') 并 stdin.flush()
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(f"STDOUT:\n{out}")
    if err:
        print(f"STDERR:\n{err}")


def upload_file(ssh_client: paramiko.SSHClient, local_path: str, remote_path: str) -> None:
    """
    使用 SFTP 将本地文件上传至远端路径。
    """
    print(f"[UPLOAD] {local_path} -> {remote_path}")
    sftp = ssh_client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()


def stop_fdb_on_servers(servers: list) -> None:
    """
    在给定列表的服务器上停止 foundationdb 服务。
    """
    for server in servers:
        with create_ssh_client(server) as ssh:
            run_remote_command(ssh, "sudo service foundationdb stop")


def start_fdb_on_servers(servers: list) -> None:
    """
    在给定列表的服务器上启动 foundationdb 服务。
    """
    for server in servers:
        with create_ssh_client(server) as ssh:
            run_remote_command(ssh, "sudo service foundationdb start")


def restart_fdb_on_server(server: str) -> None:
    """
    在给定的服务器上重启 foundationdb 服务。
    """
    with create_ssh_client(server) as ssh:
        run_remote_command(ssh, "sudo service foundationdb restart")


def prepare_remote_servers(servers: list, is_sqlite: bool) -> None:
    """
    对每个服务器执行：
    1) 停止 fdb
    2) 在 /mydata 下创建新目录（可根据实际需要添加时间戳）
    3) 上传新的 foundationdb.conf 和 storagetype.json
    4) 启动 fdb
    """
    for server in servers:
        print(f"=== 准备服务器: {server} ===")
        with create_ssh_client(server) as ssh:
            # 1) 停止 fdb
            run_remote_command(ssh, "sudo service foundationdb stop")

            # 2) 在 /mydata 下创建新目录（这里以时间戳命名）
            # timestamp_dir = time.strftime("%Y%m%d_%H%M%S")
            # remote_dir = f"{REMOTE_DATA_BASEDIR}/{"data"}"
            run_remote_command(ssh, f"sudo rm -rf /mydata/data/*")

            # 3) 上传新配置
            if server == servers[0]:
                if is_sqlite:
                    upload_file(ssh, "/users/gyming/run_ycsb/conf/foundationdb_log_sqlite.conf", REMOTE_FDB_CONF_PATH)
                else:
                    upload_file(ssh, "/users/gyming/run_ycsb/conf/foundationdb_log_cache.conf", REMOTE_FDB_CONF_PATH)
            else:
                if is_sqlite:
                    upload_file(ssh, "/users/gyming/run_ycsb/conf/foundationdb_storage_sqlite.conf", REMOTE_FDB_CONF_PATH)
                else:
                    upload_file(ssh, "/users/gyming/run_ycsb/conf/foundationdb_storage_cache.conf", REMOTE_FDB_CONF_PATH)

            # 4) 启动 fdb
            run_remote_command(ssh, "sudo service foundationdb start")


def configure_fdb():
    """
    本地执行 fdbcli 配置命令： fdbcli --exec "configure new single ssd"
    """
    print("[LOCAL CMD] fdbcli --exec 'configure new single ssd'")
    result = subprocess.run(
        ["fdbcli", "--exec", "configure new single ssd"],
        capture_output=True,
        text=True
    )
    print("STDOUT:\n", result.stdout)
    print("STDERR:\n", result.stderr)


def run_ycsb_command_load(workload_file: str, output_file: str):
    """
    本地执行 YCSB 命令，例如：
    bin/ycsb load foundationdb -P workloads/workload_xxx -threads 1 -s > xxx.txt
    """
    cmd = f"bin/ycsb load foundationdb -P {workload_file} -threads 1 -s"
    print(f"[LOCAL CMD] {cmd} > {output_file}")
    with open(output_file, "w") as f:
        proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=f, cwd="/users/gyming/YCSB/")
        _, stderr = proc.communicate()
        if stderr:
            print("YCSB STDERR:\n", stderr.decode())

def run_ycsb_command_run(workload_file: str, output_file: str):
    """
    本地执行 YCSB 命令，例如：
    bin/ycsb load foundationdb -P workloads/workload_xxx -threads 1 -s > xxx.txt
    """
    cmd = f"bin/ycsb run foundationdb -P {workload_file} -threads 1 -s"
    print(f"[LOCAL CMD] {cmd} > {output_file}")
    with open(output_file, "w") as f:
        proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=f, cwd="/users/gyming/YCSB/")
        _, stderr = proc.communicate()
        if stderr:
            print("YCSB STDERR:\n", stderr.decode())

def run_exp_item(name:str, workload_name:str, output_name:str):
    restart_fdb_on_server("apt075.apt.emulab.net")
    time.sleep(60)
    run_ycsb_command_run(f"/users/gyming/run_ycsb/workloads/{name}/{workload_name}", f"/users/gyming/run_ycsb/result/{output_name}")

def run_exp(is_sqlite: bool, name: str):
    # 第一步：在所有服务器上停止 fdb、上传配置并启动
    prepare_remote_servers(SERVERS, is_sqlite)

    # 第二步：使用本地 fdbcli 进行配置
    configure_fdb()

    # 第三步：等待 60 秒
    print("Wait 30s for cluster initialization  ...")
    time.sleep(60)

    # 第四步：执行 YCSB insert
    output_name = name + "_sqlite" if is_sqlite else name + "_cache"
    run_ycsb_command_load(f"/users/gyming/run_ycsb/workloads/{name}/workload_insert", f"/users/gyming/run_ycsb/result/{output_name}/insert.txt")

    # 第五步：对 apt144.apt.emulab.net 重启 fdb
    run_exp_item(name, "workload_read_zipfian", output_name+"/read_zipfian.txt")
    
    run_exp_item(name, "workload_read_uniform", output_name+"/read_uniform.txt")
    
    run_exp_item(name, "workload_scan_zipfian", output_name+"/scan_zipfian.txt")
    
    run_exp_item(name, "workload_scan_uniform", output_name+"/scan_uniform.txt")
    
    stop_fdb_on_servers(SERVERS)
    for server in SERVERS:
        with create_ssh_client(server) as ssh:
            run_remote_command(ssh, f"sudo cp -r /mydata/data /mydata/{output_name}")

    print("全部流程已完成。")

def main():
    # run_exp(is_sqlite=False, name="1MB")
    # run_exp(is_sqlite=True, name="1MB")
    # # run_exp(is_sqlite=False, name="1MB")
    # run_exp(is_sqlite=True, name="10MB")
    # run_exp(is_sqlite=False, name="10MB")
    # run_exp(is_sqlite=True, name="100MB")
    # run_exp(is_sqlite=False, name="100MB")
    # run_exp(is_sqlite=True, name="1GB")
    run_exp(is_sqlite=False, name="1GB")
    run_exp(is_sqlite=True, name="8GB")
    run_exp(is_sqlite=False, name="8GB")
    run_exp(is_sqlite=True, name="16GB")
    run_exp(is_sqlite=False, name="16GB")
    run_exp(is_sqlite=True, name="32GB")
    run_exp(is_sqlite=False, name="32GB")
    
if __name__ == "__main__":
    main()
