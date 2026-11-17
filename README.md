# Koikoi-Iris-WorldPack

Koikoi 是 RIA & TRIALHAMMER 联合活动服务器“鱼来”所使用的世界地形包，基于 Iris `Overworld V4005` 制作。

地图核心特色为斑驳森林，通过 Iris 提供的高度图与群系遮罩功能在地图中心生成大型湖泊作为活动中心。实际活动世界使用固定种子 `864242790704001629`。

因 Iris 4.3.6 及以上版本对水体生成逻辑进行了修改，本包对新版 Iris 不兼容，最高可使用 4.3.5 版本，不会提供向上更新的修复。

Due to Hydrology generation change implemeted in Iris 4.3.6 (and greater), this pack is only compatible with Iris under 4.3.5 and will not be upgraded.

本地形包制作过程中使用了大语言模型进行辅助开发。

This pack is developed with assistance of Large Language Models.

## 主要修改

1. （核心修改）通过程序化生成的地形高度图与世界群系遮罩，固定中央区域地表生成。
2. 下调了自然水体生成率，提高了硫磺洞穴生成率
3. 提高了废弃营地生成率，并自定义了放置算法，在放置时添加随机扰动

## 上游

Iris 项目与上游 Overworld 内容的许可和作者信息见包内 `IrisDimensions-license.md` 及上游项目说明。
