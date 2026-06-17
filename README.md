# 网络设备配置自动备份与部署系统

## 环境信息

| 项目 | 详情 |
|------|------|
| 宿主机 | Windows 11, Python 3.13 |
| 模拟器 | eNSP (华为) |
| 互联方式 | VMware VMnet1 (仅主机模式, 192.168.76.0/24) |
| 版本管理 | Git + GitHub |

## 拓扑

```
[宿主机 192.168.76.1] ----VMnet1---- [eNSP AR路由器 192.168.76.2]
```

## eNSP 与宿主机互通排障记录

### 零、失败方案

| 尝试 | 结果 | 原因 |
|------|------|------|
| VirtualBox Host-Only 网卡 | 不通 | eNSP Cloud 对 VirtualBox 网卡兼容差 |
| Microsoft KM-TEST 环回适配器 | eNSP Cloud 看不见 | eNSP 版本 Bug, 无法识别此网卡 |

### 一、最终成功方案 (VMware VMnet1)

**1.1 VMware 设置**

VMware → 编辑 → 虚拟网络编辑器 → VMnet1 → 仅主机模式
- 子网: 192.168.76.0, 掩码 255.255.255.0
- 宿主机 IP 自动变为 192.168.76.1

**1.2 eNSP Cloud 绑定**

双击 Cloud → 绑定信息 → 选择 `VMware Virtual Ethernet Adapter for VMnet1` → 点"增加" → 左侧出现端口号。

路由器接线到 Cloud 对应的端口号。

**1.3 路由器接口配置**

```
int GigabitEthernet0/0/0
 ip addr 192.168.76.2 24
 undo shutdown
```

**1.4 验证**

宿主机 PowerSell: `ping 192.168.76.2`
路由器 CLI: `ping 192.168.76.1`

### 二、常见坑点

- **Cloud 没点"增加"**: 选网卡后必须点增加按钮，否则线路上没有逻辑连接
- **接线端口不匹配**: 路由器要接到 Cloud 显示的那个端口编号上
- **接口没 undo shutdown**: 华为设备接口默认 shutdown，必须手动开启
- **防火墙拦截**: 必要时临时关闭: `Set-NetFirewallProfile -Enabled False`
- `dis ip int brief` 确认接口状态为 `up/up` 再 ping

### 三、配置路由器 Telnet 远程管理

```
system-view
 aaa
  local-user admin password cipher admin123
  local-user admin privilege level 15
  local-user admin service-type telnet
  quit
 user-interface vty 0 4
  authentication-mode aaa
  protocol inbound telnet
  quit
```

验证: 宿主机 `telnet 192.168.76.2` 能登录。

---

## 项目: network-backup

### 文件结构

```
network-backup/
├── backup.py              # 配置备份: 登录设备 → display current-configuration → 存入 configs/
├── deploy.py              # 配置部署: 读取 config_commands.txt → 逐行推送 → save
├── devices.yaml           # 设备列表 (IP/用户名/密码/协议)
├── config_commands.txt    # 要推送给设备的配置命令
├── configs/               # 备份文件目录 (每次自动带时间戳)
├── logs/                  # backup.log + deploy.log
├── requirements.txt       # Python 依赖
└── .gitignore
```

### 依赖

```
netmiko>=4.0.0
pyyaml>=6.0
```

安装: `pip install -r requirements.txt`

### 备份 (backup.py)

```
python backup.py
```

流程:
1. 读取 `devices.yaml` 中的设备列表
2. 逐台 SSH/Telnet 登录
3. 执行 `display current-configuration`
4. 保存到 `configs/设备名_时间戳.txt`
5. `git add configs/ logs/` → `git commit -m "设备配置备份 - 2026-xx-xx"`

### 部署 (deploy.py)

```
python deploy.py
```

1. 编辑 `config_commands.txt`，写入要推送的配置命令
2. 运行脚本 → 登录设备 → 进入 `system-view` → 逐行推送 → `save`

### 添加更多设备

在 `devices.yaml` 中追加:

```yaml
- device_type: huawei
  ip: "192.168.76.3"
  username: "admin"
  password: "admin123"
  name: "eNSP-SW01"
  protocol: telnet
```

### Git + GitHub 版本管理

备份后自动 Git commit。配置 GitHub 自动 push:

```bash
git remote add origin https://github.com/你的用户名/仓库名.git
```

然后修改 `backup.py` 底部:

```python
GIT_REMOTE = "origin"    # 改成 "origin" 启用自动 push
```

### 定时自动备份 (Windows 任务计划)

1. 打开 `taskschd.msc` (任务计划程序)
2. 创建任务 → 触发器: 每天 23:00
3. 操作: 启动程序 `python`, 参数 `D:\kongbai\network-backup\backup.py`
4. 起始于: `D:\kongbai\network-backup`

---

## 简历项目描述模板

### 项目名称: 网络设备配置自动备份与版本管理系统

**技术栈**: Python, Netmiko, YAML, Git, eNSP, VMware

**项目描述**:
设计并实现了一套网络设备配置自动化管理工具, 涵盖备份、部署和版本控制三个环节:
- 使用 Netmiko 库实现华为/思科多型号设备的 Telnet/SSH 自动登录与命令执行
- 支持 YAML 批量管理设备列表, 一键备份多台设备的运行配置并带时间戳归档
- 集成 Git 版本管理, 每次备份自动 commit, 可追溯配置变更历史
- 编写配置部署模块, 支持将标准化的配置命令批量推送到设备
- 在 eNSP 模拟环境中完成端到端验证, 掌握了 Cloud 互通排障、VTY 远程管理等实操技能

**个人贡献**: 独立完成脚本编写、eNSP 环境搭建、VMware 网络调通、Git 工作流集成。

---

## 后续扩展方向

- 加入邮件/钉钉告警, 备份失败自动通知
- 加入 diff 对比, 检测两次备份间的配置差异
- 支持 SFTP 将备份文件上传到集中存储服务器
- 多线程并发备份, 提升大批量设备处理速度
