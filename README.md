# Pointercrate Top 150 玩家 Hardest 统计

通关数据快照：**2026 年 10 月 24 日 11:35（北京时间）**。这是固定快照，后续榜单变化不会自动更新本页。

**Hardest 位于当时 Top 1–150 的共有 2,952 人（包含 verifier）。**
本页的分布图、累计图、高峰明细和精细视图统一按玩家 ID 去重；每人只归入其最难通关的名次。

## 各名次人数（包含 verifier）

![各名次 Hardest 人数：平方根纵轴与 Main / Extended List 分界](hardest_distribution.png)

- 纵轴采用**平方根刻度**，刻度标签仍是实际人数。1–25 人的小柱更清楚，最大值仍完整保留；柱高不再与人数成线性比例。
- 每位玩家只归到其最难通关的名次（其已完成关卡中最小的排名数字）。零人数用灰点表示。
- 橙色为明显高于周围的柱子；高峰明细保留排名、关名和人数。
- **大虚线**位于 #75 / #76 之间，区分 **Main List（#1–75）/ Extended List（#76–150）**。

### 为什么包含 verifier 仍有零值？

**零值表示没有玩家把该关作为其 Hardest，而不是该关没有通关者或验证者。** 当验证者通关过更难关卡时，就计入更高名次。

例如：#5 **Amethyst** 的 verifier **wPopoff** 已计入其更难的通关 **#3 Society**，所以 #5 可以为零。#14 **The Bloop** 的 verifier **Zoink** 归在 **#2 Artemis 13**。已逐个核对全部 20 个零值关卡；[完整核对表](zero_bin_audit.csv)列出每关的通关人数、verifier 及其 Hardest 归属。

## 累计人数与比例（包含 verifier）

![前 N 名累计去重人数与样本占比](hardest_cumulative.png)

绿色柱为至少通关过前 N 名中一关的累计去重人数。**它直接由上图的同一组含 verifier 人数，从第 1 名起逐柱累加得到**；纵轴保持线性，百分比以全部 2,952 人为分母。

已用 10,729 条已批准记录与 150 个关卡的 verifier 信息复算：150 个名次的分布与累计值逐项一致。第 1–10 名各柱之和为 15，累计图 Top 10 也是 15；第 1–150 名各柱之和为 2,952。

| 范围 | 累计人数（含 verifier） |
| --- | ---: |
| Top 10 | 15 |
| Top 30 | 241 |
| Top 50 | 667 |
| Top 75 | 1,030 |
| Top 100 | 1,503 |
| Top 125 | 2,173 |
| Top 150 | 2,952 |

## 高峰关卡明细

筛选规则：Hardest 人数至少 35 人，且至少为前后各 4 名关卡人数中位数的 3 倍（中位数小于 1 时按 1 计算）。这里只描述人数集中程度，不推断原因或难度异常。

| 排名 | 关名 | Hardest 人数（含 verifier） |
| ---: | --- | ---: |
| 18 | Silent clubstep | 39 |
| 28 | Acheron | 63 |
| 33 | Kyouki | 54 |
| 40 | Slaughterhouse | 164 |
| 49 | Sakupen Circles | 75 |
| 60 | Firework | 98 |
| 65 | poocubed | 54 |
| 68 | Saul Goodman | 55 |
| 80 | Sevvend Clubstep | 37 |
| 81 | Edge of Destiny | 39 |
| 84 | Solar Flare | 81 |
| 86 | LIMBO | 130 |
| 93 | The Plunge | 48 |
| 119 | Sonic Wave Infinity | 87 |
| 120 | Tartarus | 277 |
| 131 | The Golden | 243 |
| 132 | Oblivion | 144 |
| 137 | Verdant Landscape | 45 |
| 141 | UNKNOWN | 119 |
| 143 | Shukketsu | 74 |

## 逐柱精细视图

每张仅展示 50 个名次，柱顶直接写出人数。三张均包含 verifier，并使用相同的平方根纵轴。

<details>
<summary>展开查看 #1–50</summary>

![第 1–50 名：逐柱人数](hardest_detail_1_50.png)

</details>

<details>
<summary>展开查看 #51–100</summary>

![第 51–100 名：逐柱人数](hardest_detail_51_100.png)

</details>

<details>
<summary>展开查看 #101–150</summary>

![第 101–150 名：逐柱人数](hardest_detail_101_150.png)

</details>

## 数据来源与口径

- 按 Pointercrate 玩家 ID 去重，将公开已批准的 100% 记录与榜单验证者合并；同一人即使有多条记录或验证多个关卡，也只按其最靠前的已通关名次归类一次。
- CSV 中的 `approved_records_only` 字段属于对照数据；本页所有图表均使用 `including_verifiers` 系列。绘图脚本检查每个名次的累计值是否等于前面各柱之和。
- 不包含未提交的实际通关。抓取前后，前 150 名的排名和验证者一致；通关记录为抓取期间取得的数据，并非数据库的原子快照。
- 来源：[Pointercrate](https://pointercrate.com/)。

## 下载与复现

[总览 PNG](hardest_top150_charts.png) · [矢量 SVG](hardest_top150_charts.svg) · [PDF](hardest_top150_charts.pdf)

[150 个名次的统计 CSV](hardest_by_rank.csv) · [高峰关卡 CSV](peak_levels.csv) · [零值核对表](zero_bin_audit.csv) · [统计汇总 JSON](summary.json)

安装 Python 的 `matplotlib` 和 `numpy` 后，在仓库根目录运行：

```bash
python scripts/render_charts.py
```

该命令仅使用仓库内的 CSV 和 JSON 重绘，不抓取新通关记录，不改变统计快照。
