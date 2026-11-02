# Koikoi

Koikoi 是面向短期 Minecraft 活动服务器的 Iris 地形包，基于 Iris `Overworld V4005` 包制作，适用于 Minecraft 26.3。地图以原版斑驳森林为核心主题，在保留 Iris 幻想风格地形、洞穴、水文、装饰和原版结构兼容性的基础上，加入中心活动湖及其周边活动区域。

活动世界使用固定种子 `864242790704001629`，作者地图使用布局种子 `3560224932`。预览世界名称为 `iris:koikoi_preview`。

因 Iris 4.3.6 及以上版本对水体生成逻辑进行了修改，本包对新版 Iris 不兼容，最高可使用 4.3.5 版本。

## 地图特色

- 中心湖位于世界 `(0, 0)`，水面高度为 Y=50，作者水面约 46,080 格。
- 湖泊轮廓由六个旋转湖瓣、连续坐标扰动和深入陆地的湾口组成，边界曲折且没有矩形裁切。
- 湖岸具有连续的高度过渡和小尺度噪声起伏；湖底包含浅坡、浅脊、凹槽以及沙、黏土、泥土、沙砾、石头和安山岩等材质斑块。
- 湖泊、湖岸和核心森林使用 `minecraft:dappled_forest` 原版身份，同时保留多个 Iris 斑驳森林衍生群系，用于区分树木、地表装饰和湖底材质。
- 核心区向外通过高度、区域和群系蒙版平滑过渡到 Iris 原生地形。人工定义的东北孤立山峰已移除，外围山地和幻想风格地形仍可生成。
- 保留海洋、河流、山地、森林、冻原、沼泽、热带和其他原版衍生群系；海洋出现率通过 `landChance=0.95` 降低，但海洋定义没有删除。
- 保留 Iris 三维噪声洞穴、随机地表破洞、地下河、海岸洞穴、自然水文、矿物和地表装饰。
- 提高硫磺柱廊候选生成率，并在固定活动种子下提供一个大型核心硫磺洞室，包含硫磺围岩、朱砂、硫磺尖刺和底部岩浆。
- 废弃营地使用按区块概率采样的群系级原版结构放置，保留原版营地变体、模板和战利品，同时避免固定的 9 区块结构网格。

## 地形控制方式

当前维度配置使用四张源图片以及对应的蒙版和颜色映射定义：

- `activity/terrain-mask`：限制自定义高度场的作用范围。
- `activity/lake-height`：控制湖泊、湖岸和核心周边的连续高度场。
- `activity/forest-region-mask` 与 `activity/forest-region`：控制核心区域的 Iris 区域身份。
- `activity/surface-biomes-mask` 与 `activity/surface-biomes`：控制核心地表群系分布。

图片地图为 `1025×1025`，中心对应世界 `(0, 0)`。它们只控制活动核心及其平滑过渡带，地图外围仍由 Iris 原有噪声、区域、群系和地形机制生成。

## 群系注册与本地化

Iris 群系文件中的 `derivative`、`vanillaDerivative` 和 `customDerivitives` 作用不同。只有 `customDerivitives` 会产生游戏内 Iris 自定义群系注册名称。当前 Koikoi 有 145 个客户端翻译键，格式为 `iris.biome.koikoi/<customBiomeId>`；例如：

```json
{
  "iris.biome.koikoi/tropical_plains": "热带平原"
}
```

资源包应将翻译写入 `assets/iris/lang/zh_cn.json`。当前 Iris 还会为这些自定义群系生成内容寻址的注册资源键 `iris:biomes/<sha256>`，列表中同时记录了翻译键、源定义和实际注册资源。核心 `dappled/lake`、湖岸和森林使用原版 `minecraft:dappled_forest` 身份，但没有因此创建独立的 `iris.biome.koikoi/dappled_*` 翻译键。

完整注册键表见：

- [Iris 自定义群系注册键名表（Markdown）](docs/群系键名列表.md)
- [Iris 自定义群系注册键名表（JSON）](docs/biome-keys.json)

## 主要参考文件

- [地图设计说明](docs/地图设计.md)
- [活动区域参数](docs/event-world.json)
- [维度配置](dimensions/koikoi.json)
- [作者地图参数](docs/activity-map.json)
- [活动地图生成工具](tools/build_activity_maps.py)
- [VSCode Workspace](koikoi.code-workspace)

打开 `koikoi.code-workspace` 可以使用包内 Iris schema、定义跳转和补全功能。修改图片地图或生成定义后，应重新执行 Iris 包校验，并创建新的预览世界查看效果。

## 上游来源

Koikoi 基于 Iris `Overworld V4005` 地形包制作。上游包提供基础的 Overworld 区域、原版衍生群系、洞穴、水文、矿物、装饰、对象和结构适配机制；Koikoi 在此基础上增加活动区域图片地图、斑驳森林核心主题、湖泊与湖底变体、核心硫磺洞室以及随机化废弃营地放置。

Iris 项目与上游 Overworld 内容的许可和作者信息见包内 `IrisDimensions-license.md` 及上游项目说明。
