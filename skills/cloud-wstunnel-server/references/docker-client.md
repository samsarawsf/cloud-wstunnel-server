# Docker 管理持续应用转发

默认将每个持续应用映射作为独立 Compose 服务，`restart: unless-stopped`，以 detached 模式启动。工具会话仅作短时诊断；退出原因不明时保留证据，不把 Docker 化表述为已证实解决所有隔夜中断。

## 部署前确认

- 读取当前云 runtime 的 Docker 文档，核实托管 Docker 守护进程可用。保留平台配置、代理和注册表凭证；不另起守护进程，不为转发重启全部容器。
- 核实架构并使用已验证版本/校验值的 wstunnel 二进制。镜像固定版本，部署登记记录 digest；不要将隧道凭证或平台代理 CA 烘焙进镜像。
- 从已有 Docker 配置和当前 runtime 确认**容器可达的**代理地址。外层的 `proxy` 主机名或环境变量不会自动在内层可用；需要地址映射时按 runtime 添加。不清空代理、放大 NO_PROXY 或以 host 网络绕过策略。
- 确定实际应用网络、服务 DNS 名和容器内端口。优先把转发容器加入已有应用网络，不发布客户端端口、不加入数据库网络。`depends_on`、容器 running 或 Compose 启动成功均不能证明实际隧道健康。

宿主机应用若只监听127.0.0.1，桥接容器的 `host-gateway` 不能直接访问它。平台明确支持且符合网络策略时才可采用 host 网络以访问宿主机回环，仍保留全部代理/CA；否则使用支持的应用网络接入方式，不擅自改为公网监听。

## 可适配的 Compose 模板

以下示例要求镜像含 `/bin/sh` 和 `/usr/local/bin/wstunnel`。可基于已固定 digest 的可信精简基础镜像复制已校验的静态二进制自行构建；若镜像不含 shell，应另行实现从秘密文件读取凭证的入口，不把秘密硬编码进 Compose。

`deployment.env` 仅存非秘密参数，设为0600并排除版本库。代理若含认证信息，应按私密配置处理；不得输出完整 Compose 展开结果。

```yaml
services:
  app-tunnel:
    image: ${WSTUNNEL_IMAGE:?fixed tested image required}
    restart: unless-stopped
    init: true
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    environment:
      NO_COLOR: "true"
      HTTP_PROXY: ${TUNNEL_HTTP_PROXY:?container-reachable platform proxy required}
      HTTPS_PROXY: ${TUNNEL_HTTPS_PROXY:?container-reachable platform proxy required}
      NO_PROXY: ${TUNNEL_NO_PROXY:-}
      SSL_CERT_FILE: /run/platform-ca.pem
      TLS_NAME: ${TLS_NAME:?}
      PUBLIC_IP: ${PUBLIC_IP:?}
      WSS_PORT: ${WSS_PORT:-443}
      REVERSE_BIND: ${REVERSE_BIND:?}
      REVERSE_PORT: ${REVERSE_PORT:?}
      TARGET_HOST: ${TARGET_HOST:?application service DNS required}
      TARGET_PORT: ${TARGET_PORT:?application container port required}
    secrets:
      - tunnel_auth_path
    volumes:
      - type: bind
        source: ${TUNNEL_CA_BUNDLE:?current trusted combined CA bundle required}
        target: /run/platform-ca.pem
        read_only: true
    networks:
      - application
    entrypoint: ["/bin/sh", "-ec"]
    command:
      - |
        auth_path="$$(cat /run/secrets/tunnel_auth_path)"
        test -n "$$auth_path"
        exec /usr/local/bin/wstunnel client \
          --tls-verify-certificate --tls-sni-override "$$TLS_NAME" \
          -P "$$auth_path" \
          -R "tcp://$$REVERSE_BIND:$$REVERSE_PORT:$$TARGET_HOST:$$TARGET_PORT" \
          "wss://$$PUBLIC_IP:$$WSS_PORT"
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
secrets:
  tunnel_auth_path:
    file: ${AUTH_PATH_FILE:?existing restricted credential file required}
networks:
  application:
    external: true
    name: ${APP_NETWORK:?existing application network required}
```

只读挂载当前有效的 CA bundle，既包含平台代理信任也保留正常根证书。凭证源文件权限0600，镜像运行用户必须能读取所挂载文件；Compose 文件秘密不等于加密秘密存储。保持 WSS 入口原有 TLS 身份验证。该例不需要端口发布、特权模式或 Docker socket 挂载。若应用网络是 internal 网络且不可达代理，在平台允许范围内另外加入专用出口网络，并实际验证代理可达。

## 启动、迁移和验证

1. 对 Compose 做静态校验，不输出解析后的秘密：

   ```sh
   docker compose --env-file deployment.env -f compose.tunnel.yaml config --quiet
   docker compose --env-file deployment.env -f compose.tunnel.yaml up -d app-tunnel
   ```

2. 检查该服务状态及选择性 inspect 字段：容器 ID、State.Status、ExitCode、OOMKilled、RestartCount、RestartPolicy.Name。日志使用有界读取，展示前按实际凭证值脱敏；`-P` 参数仍可能通过进程参数和日志出现，不公开完整 inspect/env/process 输出。
3. 从用户设备检查真实 VPS 入口、登录跳转和资源；连续两次实际请求成功，且启动命令已结束后的另一次工具调用仍能访问。不能只验证容器内应用或 VPS 443。
4. 迁移原工具客户端时，先批准一个临时空闲反向端口并在其上验证新容器，再停止记录的旧客户端，改为原端口并只重建转发服务。若旧客户端已退出，可直接使用原端口。不得同时用两个客户端争抢原端口；失败时恢复旧映射，移除临时端口授权，不重建应用数据库。
5. 在本次部署授权范围内验证**意外退出恢复**：容器稳定运行至少10秒后，对已记录容器内的 wstunnel 进程发送终止信号，观察退出与自动重启，确认 RestartCount 增长并再次检查用户入口。镜像支持 `docker exec ... kill` 时可用；不支持则选适用的容器内信号方式。不用 `docker stop` 或 `docker compose stop` 模拟崩溃——它们属于人为停止，会抑制自动重启。不为测试重启 Docker 或云环境，不中断未授权的其他服务。
6. 若本次不能执行恢复测试，登记“已配置，尚未实测”；不将重启策略存在作为恢复通过的证据。长时间观察仅在用户授权后进行。

## 管理和恢复边界

复用上方 `--env-file` 与 `-f` 参数：`logs --tail 100 app-tunnel` 查看日志，`stop app-tunnel` 主动停止，`start app-tunnel` 恢复人工停止的服务。排障修改配置后使用 `up -d app-tunnel` 仅重建隧道；不执行整个项目的 `down -v`。

- `unless-stopped` 覆盖客户端正常/异常退出；人为停止后保持停止，不用自动化把它强行启动。
- Docker 的重启策略不因 healthcheck 为 unhealthy 自动重启，也不证明 WSS 可达。进程存活但断线时检查重连日志、代理、证书、服务端限制和应用目标。
- 平台暂停、Docker 守护进程不可用或环境删除无法由客户端容器自行恢复。环境替换时重建镜像/网络/凭证和 CA 挂载，核实数据恢复；旧会话的代理地址或 CA 可能已失效。
- 部署登记保存 Compose、镜像 digest、网络/目标、凭证文件位置（不含值）、重启策略、日志命令及实际测试结果。独立的健康转发若保留为持续服务，同样采用容器管理。

参考：[Docker 自动重启语义](https://docs.docker.com/engine/containers/start-containers-automatically/)、[wstunnel 参数](https://github.com/erebe/wstunnel)。模板需按实际环境适配，尚未代表目标云环境中的实测部署。
