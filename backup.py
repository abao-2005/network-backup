"""
==========================================================================
网络设备配置自动备份脚本
功能：
  1. 读取 devices.yaml 里的设备列表
  2. 逐个 SSH 登录设备
  3. 执行 display current-configuration 命令
  4. 把配置保存到 configs/ 目录
  5. 备份日志写入 logs/backup.log
==========================================================================
"""

# ========== 第1部分：导入模块（import） ==========
# Python 里，模块就是别人写好的代码包，我们直接拿来用
import yaml                      # 用来读取 YAML 文件（devices.yaml）
import os                        # 用来操作文件和目录（创建文件夹等）
import subprocess                # 用来执行外部命令（git 操作）
import logging                   # 用来写日志
from datetime import datetime    # 用来获取当前时间（用于文件名）
from netmiko import ConnectHandler  # Netmiko 是连接网络设备的库，支持 SSH 和 Telnet


# ========== 第2部分：配置日志 ==========
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)  # 如果 logs 文件夹不存在，就创建它

logging.basicConfig(
    filename=os.path.join(log_dir, "backup.log"),  # 日志文件路径
    level=logging.INFO,   # 记录 INFO 及以上级别的日志
    format="%(asctime)s - %(levelname)s - %(message)s"  # 日志格式：时间 - 级别 - 内容
)
logger = logging.getLogger(__name__)  # 创建一个日志记录器对象


# ========== 第3部分：定义函数 ==========
# 函数就是一段可以重复使用的代码块，用 def 关键字定义

def load_devices(yaml_file: str) -> list:
    """
    读取 YAML 文件，返回设备列表
    参数:
        yaml_file: YAML 文件的路径
    返回:
        list: 设备字典列表，例如 [{"ip": "1.1.1.1", "username": "admin", ...}, ...]
    """
    with open(yaml_file, "r", encoding="utf-8") as f:  # 打开文件，'r' 表示只读
        devices = yaml.safe_load(f)  # safe_load 把 YAML 内容转成 Python 列表
    print(f"从 {yaml_file} 中读取到 {len(devices)} 台设备")
    logger.info(f"读取设备列表成功，共 {len(devices)} 台设备")
    return devices


def backup_single_device(device: dict) -> bool:
    """
    连接单台设备，备份配置
    参数:
        device: 设备信息字典，包含 ip, username, password, name, device_type
    返回:
        bool: True=备份成功, False=备份失败
    """
    device_name = device["name"]       # 取出设备名称
    device_ip = device["ip"]           # 取出设备IP

    print(f"\n{'='*40}")
    print(f"正在备份: {device_name} ({device_ip})")
    logger.info(f"开始备份 {device_name} ({device_ip})")

    # 构建连接参数，Netmiko 需要这些字段
    # .get(key, 默认值) 是字典的安全取值方法：如果 key 不存在，返回默认值
    dev_type = device["device_type"]   # 设备类型，如 'huawei'
    protocol = device.get("protocol", "ssh").lower()  # 协议，默认 ssh
    port = device.get("port", None)  # 端口号，不写则用默认（SSH=22, Telnet=23）

    # 如果是 telnet 且 device_type 没有 _telnet 后缀，自动追加上去
    # 因为 Netmiko 里华为的 SSH 用 "huawei"，Telnet 用 "huawei_telnet"
    if protocol == "telnet" and not dev_type.endswith("_telnet"):
        dev_type = dev_type + "_telnet"

    connection_params = {
        "device_type": dev_type,
        "host": device["ip"],
        "username": device.get("username", ""),
        "password": device.get("password", ""),
        "conn_timeout": 15,  # 连接超时时间（秒）
    }
    # 如果指定了端口号，加入连接参数；没指定则用协议默认端口
    if port:
        connection_params["port"] = port

    try:
        # ---- 连接设备 ----
        print(f"  → 正在连接 {device_ip} (协议: {protocol.upper()}) ...")
        net_connect = ConnectHandler(**connection_params)
        print(f"  → 连接成功！")

        # ---- 执行命令 ----
        print(f"  → 正在执行: display current-configuration ...")
        output = net_connect.send_command("display current-configuration")
        # send_command 执行命令，返回命令的输出（字符串）

        # ---- 断开连接 ----
        net_connect.disconnect()
        print(f"  → 已断开连接")

        # ---- 保存配置到文件 ----
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 生成时间戳，如 20260617_153020
        filename = f"{device_name}_{timestamp}.txt"  # 文件名：设备名_时间戳.txt
        filepath = os.path.join("configs", filename)  # 文件路径：configs/设备名_时间戳.txt

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output)  # 把命令输出写入文件

        file_size = len(output)  # 获取配置内容的大小（字符数）
        print(f"  [OK] 备份完成: {filepath} ({file_size} 字符)")
        logger.info(f"[OK] {device_name} 备份成功 -> {filepath} ({file_size} 字符)")
        return True

    except Exception as e:
        # try...except 是异常处理：如果 try 里面的代码出错，就执行 except 块
        error_msg = f"[FAIL] {device_name} ({device_ip}) 备份失败: {e}"
        print(f"  {error_msg}")
        logger.error(error_msg)
        return False


def git_commit_and_push(remote: str = "", branch: str = "main") -> bool:
    """
    把备份文件 git add → commit → push 到远程仓库
    参数:
        remote: 远程仓库名称（如 origin）。为空则不 push，只本地 commit
        branch: 分支名
    返回:
        bool: 是否成功
    """
    print(f"\n{'='*40}")
    print(f"正在提交到 Git ...")

    try:
        subprocess.run(["git", "add", "configs/", "logs/"], check=True)
        logger.info("git add 完成")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"设备配置备份 - {timestamp}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        print(f"  -> git commit 成功: {commit_msg}")
        logger.info(f"git commit 成功: {commit_msg}")

        if remote:
            print(f"  -> 正在 git push {remote} {branch} ...")
            subprocess.run(["git", "push", remote, branch], check=True)
            print(f"  -> git push 成功！")
            logger.info(f"git push {remote} {branch} 成功")
        else:
            print(f"  -> 未配置远程仓库，跳过 push")
            print(f"  -> 提示: 设置远程仓库后会自动 push:")
            print(f"       git remote add origin <你的仓库地址>")
            logger.info("未配置远程仓库，仅做了本地 commit")

        return True

    except subprocess.CalledProcessError as e:
        error_msg = f"[FAIL] Git 操作失败: {e}"
        print(f"  {error_msg}")
        logger.error(error_msg)
        return False


def main() -> None:
    """
    主函数：程序的入口
    先读取设备列表，再逐台备份
    """
    print("=" * 50)
    print("  网络设备配置自动备份工具 v1.0")
    print("=" * 50)

    # ---- 确保备份目录存在 ----
    os.makedirs("configs", exist_ok=True)

    # ---- 加载设备列表 ----
    devices = load_devices("devices.yaml")

    # ---- 逐台备份 ----
    success_count = 0   # 成功计数器（初始值 0）
    fail_count = 0      # 失败计数器

    for device in devices:  # for 循环：遍历 device 列表中的每台设备
        ok = backup_single_device(device)  # 调用备份函数
        if ok:
            success_count += 1   # success_count = success_count + 1
        else:
            fail_count += 1

    # ---- 打印汇总 ----
    print(f"\n{'='*50}")
    print(f"  备份完成！成功: {success_count} 台，失败: {fail_count} 台")
    print(f"  备份文件保存在: configs/ 目录")
    print(f"  日志文件保存在: logs/backup.log")
    print(f"{'='*50}")
    logger.info(f"备份任务结束 — 成功: {success_count}, 失败: {fail_count}")

    # ---- 自动提交到 Git ----
    # 如果有远程仓库，请在这里设置地址：
    #   先运行: git remote add origin https://github.com/你的用户名/仓库名.git
    #   然后改下面的 GIT_REMOTE = "origin"
    GIT_REMOTE = "origin"     # 自动 push 到 GitHub
    GIT_BRANCH = "main"
    git_commit_and_push(remote=GIT_REMOTE, branch=GIT_BRANCH)


# ========== 第4部分：程序入口 ==========
# 这行代码的意思是：当直接运行这个 .py 文件时，执行 main() 函数
# 如果这个文件被其他文件 import，则不会自动执行 main()
if __name__ == "__main__":
    main()
