物业收费登记（macOS）使用说明
================================

本安装包为 Intel (x86_64) 架构，适用于：
- Intel 芯片 Mac（原生运行）
- Apple Silicon (M1/M2/M3…) Mac（通过 Rosetta 运行）

【数据存储】
打包版数据固定保存在：
  ~/Library/Application Support/Tally/data
不可更改。请定期备份该目录。

【卸载】
打开应用 → 通用配置 → 卸载应用。
将删除 Tally.app、上述数据目录及相关配置。

【首次打开提示“无法打开 / 已损坏”时】
因为应用未做苹果开发者签名，系统会拦截。请任选其一：

方法 A（推荐）：
1. 将 Tally.app 拖到「应用程序」或任意本地文件夹
2. 按住 Control 键点击 Tally.app → 选择「打开」→ 再点「打开」

方法 B（终端）：
  xattr -cr /path/to/Tally.app
