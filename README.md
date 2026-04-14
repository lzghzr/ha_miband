## MiBand
将 小米手环、手表 的 BLE 广播消息添加到 Home Assistant


### 使用方法
1. 设备必须支持米家，比如小米手环10，小米手表4、5等
2. 必须有蓝牙网关，可以使用esp32自制 [CT30W 增加射频模块，更换ESP32C3](https://bbs.hassbian.com/thread-30428-1-1.html)
3. 手环触发任意状态，比如穿戴，即可在HA中显示

### 其它说明
此集成基于 [xiaomi_ble](https://github.com/home-assistant/core/tree/dev/homeassistant/components/xiaomi_ble)，之所以没有合并到 xiaomi_ble，有几个原因
1. 小米可穿戴设备的`beaconkey`获取方式不同，目前无法并入，以后找到方法的话会尝试合并
2. 小米可穿戴设备的运动类型，在使用`translation_key`后，反而不支持直接输入自然语言，比如 `"自由训练"`，必须使用`"free_training"`，目前没有找到方法解决
3. 小米可穿戴设备的睡眠状态可能会添加其它属性，比如"Light Sleep"，"Deep Sleep"，合并到官方集成如需更改会比较困难
