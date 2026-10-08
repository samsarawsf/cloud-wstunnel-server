# 中转部署与连接模板

下列变量从用户授权的服务器和本次检查取得，不使用历史部署值。`REVERSE_BIND` 优先选 VPS Tailscale IPv4；回环绑定适用于用户经 SSH 访问，不会自动开放到 Tailscale。

| 参数 | 含义 |
| --- | --- |
| PUBLIC_IP | 用户 VPS 公网 IPv4 |
| TAILNET_IP | 已核实的 VPS Tailscale IPv4 |
| TLS_NAME | 实际有效证书的 DNS 身份 |
| REVERSE_BIND / REVERSE_PORT | VPS 端受限反向监听地址 / 空闲端口 |
| CLOUD_PORT | 云端应用的回环监听端口 |
| DEPLOYMENT_DIR | 各执行位置独立的可写部署目录 |

## 包与 TLS

已验证的基线是官方 wstunnel v11.0.0 Linux amd64 静态包：

```text
https://github.com/erebe/wstunnel/releases/download/v11.0.0/wstunnel_11.0.0_linux_amd64.tar.gz
SHA256 9708a99717b5a951453c2ff7c14c25d3418d02ca7fcb96fdb382a8f2083bab5e
```

在执行位置核实 `uname -sm`，下载、检查哈希后再提取执行，必要时 `chmod u+x wstunnel`。其他架构或版本应查官方发布包和校验清单，不套用这个哈希。托管云端下载仍通过继承的代理及 CA。无需全局安装，也无需升级 VPS 系统。

优先使用用户已有的有效证书。若 VPS 已接入 Tailscale 且该网络已启用 HTTPS，可读取其 DNS 身份并申请该机器的证书：

```sh
tailscale cert --cert-file server.crt --key-file server.key "$TLS_NAME"
openssl x509 -in server.crt -noout -subject -issuer -dates
```

仅在确实需要时使用此方式。HTTPS 尚未启用或账户限制应通过支持的设置流程处理。不要默默启用 Funnel；拥有公网 VPS 时可以由 wstunnel 自己监听空闲公网 TLS 端口。证书申请期间可能有等待，健康状态不能代替实际握手。

TLS 证书通常对应域名而非公网 IP。客户端可连接用户的公网 IP，并用 `--tls-sni-override "$TLS_NAME"` 保持证书身份验证；本方法已有端到端实测。若使用已有公网域名且证书匹配，直接使用该域名即可。不要通过禁用验证解决身份不匹配。

## 服务端限制与启动

先检查已有鉴权文件。为新环境创建独立随机路径凭证，避免覆盖正在使用的文件；已有环境按现有授权和限制继续使用。目录及凭证文件权限限制到部署执行用户。凭证不得写入报告、公开命令示例或版本库。

```sh
(umask 077; set -C; openssl rand -hex 24 > tunnel-auth-path)
```

生成 `restrictions.yaml`，将 `AUTH_PATH` 替换为上述文件的值、绑定地址换成已核实的单一 IPv4 `/32`；下面端口只是示例，要确认未被占用：

```yaml
restrictions:
  - name: cloud-private-service
    match:
      - !PathPrefix "^AUTH_PATH$"
    allow:
      - !ReverseTunnel
        protocol: [Tcp]
        port: [19088]
        cidr: [TAILNET_IP/32]
```

`cidr` 在此限制反向监听的绑定地址，**不是客户端来源 ACL**。随机路径鉴权、TLS 及绑定地址和批准端口限制分别处理身份、传输和转发范围。反向绑定不得改成 `0.0.0.0`。部署后用真实对照请求核实限制符合预期。

在 VPS 启动（公网 443 必须为空闲；否则选已确认允许的端口，不停止其他服务）：

```sh
NO_COLOR=true ./wstunnel server \
  --restrict-config restrictions.yaml \
  --tls-certificate server.crt --tls-private-key server.key \
  wss://0.0.0.0:443
```

用平台支持的会话/进程管理方式记录 PID 和日志。VPS `nohup` 在已验证部署中可保留进程；这不代表开机自启或证书自动续期已经配置。只在用户要求持续部署时处理这些额外事项。

## 无凭证入口检查

在云端经继承代理检查，公网地址与 TLS 身份保持正确：

```sh
curl -i --connect-timeout 5 --max-time 20 \
  --connect-to "$TLS_NAME:443:$PUBLIC_IP:443" "https://$TLS_NAME/"
```

已验证 v11.0.0 的非 WebSocket 请求可返回 `400 Invalid request`，这是入口可达证据。它不能替代后续真正的隧道请求。普通沙箱错误按工具的支持流程升级同一请求；明确策略拒绝应停止并处理配置。

若 VPS 已有固定健康服务，可用它对照私网访问。若代理返回 503，再用同一代理路径请求 `https://example.com/`：普通公共网站也失败时，先检查当前环境状态，避免在错误层反复改服务器。

## 云端服务与客户端

实际应用使用其已确认的回环监听端口；例如 Docker 应用127.0.0.1:8688。只有需要诊断隧道时，才将健康脚本复制到云端部署目录，用 Python 3 执行：

```sh
python3 -u health_server.py --port 19084 --role cloud-probe
```

原实践已有文件名 experiment-auth-path；复用原部署时保留文件名和路径，不为了本文模板重命名或重新生成凭证。

仅以经授权的方式传递新环境独立鉴权路径，写入云端权限受限文件。启动客户端时在本地读取路径值，不在跨聊天报告中重复它：

```sh
AUTH_PATH=$(cat tunnel-auth-path)
NO_COLOR=true ./wstunnel client \
  --tls-verify-certificate --tls-sni-override "$TLS_NAME" \
  -P "$AUTH_PATH" \
  -R "tcp://$REVERSE_BIND:$REVERSE_PORT:127.0.0.1:$CLOUD_PORT" \
  "wss://$PUBLIC_IP:443"
```

此示例仅设本次命令的 NO_COLOR；不要替换继承的代理或秘密变量。v11.0.0 支持 `HTTP_PROXY` 与 `SSL_CERT_FILE` / `SSL_CERT_DIR` 加载系统证书。优先保留继承的证书路径；必要时依据当前平台文档指定已有 CA 文件，不能导入未经验证的证书来跳过校验。已验证环境中的路径 `/etc/ssl/certs/ca-certificates.crt` 仅为历史示例，不假设每个镜像相同。

客户端日志可能含路径凭证，保存和展示时对实际凭证值脱敏。`-P` 参数可能出现在该机器进程参数中；不要把广泛进程列表作为公开报告。后台启动不保证跨工具命令存活；使用受工具管理的运行会话并记录其生命周期。服务端可通过配置热重载加入新条目或明确端口集合，更新前备份并核实原有映射仍可访问。多云环境使用独立鉴权条目和不冲突端口；同一云环境共享条目时也只授予已批准服务端口。

## 验证与停止

实际应用从用户已加入 Tailscale 的设备打开 http://TAILNET_IP:REVERSE_PORT/，按应用实际路由检查。以下脚本仅用于可选的固定健康服务：

```sh
python3 scripts/probe.py "http://$TAILNET_IP:$REVERSE_PORT/health" \
  --expect-role cloud-probe --expect-boot-id "$CLOUD_BOOT_ID"
```

这个脚本使用正常继承代理/CA，单次有界请求并验证服务身份。若当前电脑继承代理不支持 Tailscale，应选择其正常支持的内网执行路径，不能拿这个理由绕开托管云端平台代理。仅对 `127.0.0.1` 本地检查，可使用脚本 `--direct-loopback`；该选项拒绝远端地址和重定向。

记录云端答复完成时间后再次请求，确认 boot_id 未变化、uptime 增长。长期观察需要用户授权的后续监测；没有监测时只报告实际观察窗口。停止时按记录 PID/会话停止自己的服务，不清理别人的端口或重置整套 Tailscale 配置。

官方参考：[wstunnel](https://github.com/erebe/wstunnel)、[Tailscale 证书](https://tailscale.com/kb/1153/enabling-https)。托管云网络规则以该执行环境自带 runtime 文档为准。
