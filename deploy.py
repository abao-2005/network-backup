"""
================================================================================
网络设备配置自动部署脚本
功能：
  1. 读取 config_commands.txt 里的配置命令
  2. SSH/Telnet 登录设备
  3. 进入配置模式，逐行推送命令
  4. 自动执行 save，记录结果
================================================================================
"""
import yaml
import os
import logging
from datetime import datetime
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetmikoTimeoutException, NetmikoAuthenticationException


log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "deploy.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_devices(yaml_file: str) -> list:
    with open(yaml_file, "r", encoding="utf-8") as f:
        devices = yaml.safe_load(f)
    logger.info(f"读取设备列表成功，共 {len(devices)} 台设备")
    return devices


def load_commands(txt_file: str) -> list:
    with open(txt_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    logger.info(f"读取配置命令成功，共 {len(lines)} 条")
    return lines


def deploy_to_device(device: dict, commands: list) -> bool:
    device_name = device["name"]
    device_ip = device["ip"]

    print(f"\n{'='*40}")
    print(f"正在部署: {device_name} ({device_ip})")
    logger.info(f"开始部署 {device_name} ({device_ip})，共 {len(commands)} 条命令")

    dev_type = device["device_type"]
    protocol = device.get("protocol", "ssh").lower()
    if protocol == "telnet" and not dev_type.endswith("_telnet"):
        dev_type = dev_type + "_telnet"

    connection_params = {
        "device_type": dev_type,
        "host": device["ip"],
        "username": device.get("username", ""),
        "password": device.get("password", ""),
        "conn_timeout": 15,
    }
    if device.get("port"):
        connection_params["port"] = device["port"]

    try:
        print(f"  -> 正在连接 {device_ip} (协议: {protocol.upper()}) ...")
        net_connect = ConnectHandler(**connection_params)
        print(f"  -> 连接成功！")

        print(f"  -> 正在推送 {len(commands)} 条配置命令 ...")
        output = net_connect.send_config_set(commands)
        print(f"  -> 配置推送完成")

        print(f"  -> 正在 save ...")
        save_output = net_connect.save_config()
        print(f"  -> 保存成功: {save_output}")

        net_connect.disconnect()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join("configs", f"{device_name}_deploy_{timestamp}.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(output + "\n\n" + str(save_output))

        print(f"  [OK] 部署完成，日志: {log_file}")
        logger.info(f"[OK] {device_name} 部署成功 -> {log_file}")
        return True

    except NetmikoTimeoutException:
        error_msg = f"[FAIL] {device_name} ({device_ip}) 连接超时，设备不可达"
        print(f"  {error_msg}")
        logger.error(error_msg)
        return False
    except NetmikoAuthenticationException:
        error_msg = f"[FAIL] {device_name} ({device_ip}) 用户名或密码错误"
        print(f"  {error_msg}")
        logger.error(error_msg)
        return False
    except Exception as e:
        error_msg = f"[FAIL] {device_name} ({device_ip}) 部署失败: {e}"
        print(f"  {error_msg}")
        logger.error(error_msg)
        return False


def main() -> None:
    print("=" * 50)
    print("  网络设备配置自动部署工具 v1.0")
    print("=" * 50)

    os.makedirs("configs", exist_ok=True)

    devices = load_devices("devices.yaml")
    commands = load_commands("config_commands.txt")

    print(f"\n将要推送的命令（共 {len(commands)} 条）:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")

    print()

    success_count = 0
    fail_count = 0
    for device in devices:
        ok = deploy_to_device(device, commands)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*50}")
    print(f"  部署完成！成功: {success_count} 台，失败: {fail_count} 台")
    print(f"  日志保存在: logs/deploy.log")
    print(f"{'='*50}")
    logger.info(f"部署任务结束 — 成功: {success_count}, 失败: {fail_count}")


if __name__ == "__main__":
    main()
