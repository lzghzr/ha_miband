# MiBand

在 Home Assistant 中接收小米手环和手表的蓝牙广播，用佩戴、运动、睡眠等状态或事件触发自动化。各型号可用的实体取决于设备广播的内容。

## 安装

在 Home Assistant **2026.11 及以后**，打开「设置 → Marketplace」，从链接添加 `lzghzr/ha_miband`，再选择 MiBand 安装。已安装的用户直接更新，重启 HA 后原设备和实体会继续使用。

在较早的受支持版本（2026.3–2026.10）可通过 HACS 安装。若手动安装，将本仓库的 `custom_components/miband/` 复制到 HA 配置目录的 `custom_components/` 下，然后重启 HA。

## 接入手环或手表

1. 确认型号支持米家联动，例如小米手环 10 国行版。让手环处于 HA 蓝牙适配器或蓝牙代理的接收范围内；也可以[用 ESP32 自制蓝牙网关](https://bbs.hassbian.com/thread-30428-1-1.html)。
2. 在 HA 的「设置 → 设备与服务」中打开已发现的 MiBand 设备。按提示从小米运动健康获取绑定密钥，或手动输入。
3. 添加完成后，HA 会按型号创建实体。摘戴手环或开始一次运动，收到相应广播后就会显示实际状态。对于型号清单以外、集成能解析的事件，HA 会在第一次收到时创建实体，并记录这次事件。

升级集成并重启 HA 后，已添加的设备也会补上该型号新增的实体。先前由广播发现的事件实体会沿用原 ID 和自定义名称。

本集成基于 Home Assistant 的 [xiaomi_ble](https://github.com/home-assistant/core/tree/dev/homeassistant/components/xiaomi_ble)。
