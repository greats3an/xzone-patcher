# XZone-Patcher
## 游聚 ROM 检测补丁
### 需求
安装 Python 3.8 及以上
### 使用
(以未来遗产为例)
#### 准备
1.  找到**游聚游戏平台**安装目录，如：
	`C:\Program Files (x86)\游聚游戏平台`
	该目录下应有 `bin`, `resources` 文件夹
2. 准备游戏 ROM 文件
	ROM 需求：
	- 最好是游聚版（`resources\roms` 文件夹中）改的
	- 要求日版（`jojoban.zip` 置于）且 ROM内容 以 `simm` 加密封包
	- 避免修改贴图（如 jacket dio）；同真人对线会导致双方desync (改pointers没问题)

#### 配置
1. 将 `jojoban.zip` 置于同补丁目录
2. 修改 `config.py` , 将 `xzone` 改为自己对应的安装目录

#### 开始
运行  `patch.py`，打过补丁的模拟器及其他文件会保存在 `xzone` 文件夹
此后即可将该文件夹内容覆盖至原安装目录

#### 效果
![demo](https://github.com/greats3an/xzone-patcher/blob/master/img/demo.png "观战视角")

------------

### 注意
该补丁**不可逆**；可通过重新安装游聚（不必卸载）恢复原程序；事前请务必备份好游戏 ROM

------------

### 未来遗产交流群
Q 群 94314703
