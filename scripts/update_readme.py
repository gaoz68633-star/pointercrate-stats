"""Write the traditional-list report from the same snapshot as the charts."""
import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def read_csv(name):
    with (ROOT/name).open(encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))


def main():
    summary = json.loads((ROOT/'summary.json').read_text())
    levels = json.loads((ROOT/'data/levels.json').read_text())
    assert summary['list_type'] == 'traditional_demonlist'
    assert all(d['rated'] for d in levels)
    assert [d['rated_position'] for d in levels] == list(range(1,151))
    peaks, zeros = read_csv('peak_levels.csv'), read_csv('zero_bin_audit.csv')
    total = summary['unique_players_including_verifiers']
    stamp = datetime.fromisoformat(summary['finished_at_utc']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y 年 %m 月 %d 日 %H:%M')
    text = f'''# 传统 Pointercrate Demonlist Top 150 · 玩家 Hardest 统计

**本页使用传统 Demonlist：只统计游戏内已评级关卡，以 `rated_position` 第 1–150 名为准。**
Main List 为第 1–75 名，Extended List 为第 76–150 名。综合排名 `position` 不作为本页排名依据。

快照完成时间：**{stamp}（北京时间）**。这是固定快照，后续榜单变化不会自动更新本页。

**共有 {total:,} 人至少通关传统榜前 150 名中的一关（包含 verifier，按玩家 ID 去重）。**
分布图、累计图、高峰明细和精细视图均使用同一统计口径。

## Hardest 分布（包含 verifier）

![传统榜各名次 Hardest 人数](charts/traditional/hardest_distribution.png)

- 每人只归入自己通关过的最难关卡名次（最小的 `rated_position`），在分布图中仅出现一次。
- 平方根纵轴放大小数值，刻度仍是实际人数；柱高不与人数成线性比例。
- 橙色为明显高于周围的柱子，高峰明细保留名次、关名和人数。
- 大虚线位于 #75 / #76 之间，区分 Main List 与 Extended List。
- 零值表示无人以该关为 Hardest；verifier 若通关过更难关卡，就计入更高名次。

## 累计人数（包含 verifier）

![传统榜前 N 名累计去重人数](charts/traditional/hardest_cumulative.png)

累计图直接对分布图第 1–N 名的人数求和，纵轴保持线性。百分比以全部 {total:,} 人为分母。
已对 150 个累计阈值分别核对：累计柱高与“至少通关前 N 名中一关”的玩家 ID 集合大小一致。

| 范围 | 累计人数（含 verifier） | 占全部样本 |
| --- | ---: | ---: |
'''
    for n in [1,10,30,50,75,100,125,150]:
        count = summary['cumulative_checkpoints'][str(n)]['including_verifiers']
        text += f'| Top {n} | {count:,} | {count/total:.1%} |\n'
    text += f'''
## 高峰关卡明细

共 {len(peaks)} 个高峰。筛选规则：Hardest 人数至少 35 人，且至少为前后各 4 名中位数的 3 倍（中位数小于 1 时按 1 计算）。描述人数集中程度，不推断原因。

| 传统榜排名 | 关名 | Hardest 人数（含 verifier） |
| ---: | --- | ---: |
'''
    for row in peaks:
        text += f"| {row['rank']} | {row['level_name']} | {row['hardest_players_including_verifiers']} |\n"
    text += f'\n## 零值核对\n\n已核对 {len(zeros)} 个零值关卡，verifier 均已计入其更难通关的名次。\n\n'
    for row in zeros[:2]:
        text += f"- #{row['rank']} {row['level_name']} 的 verifier **{row['verifier_name']}**，归入 **#{row['verifier_hardest_rank']} {row['verifier_hardest_level']}**。\n"
    text += '\n[完整零值核对表](zero_bin_audit.csv)同时列出每关通关人数与 verifier 的 Hardest 归属。\n\n## 逐柱精细视图\n\n三张图使用同一平方根纵轴范围，柱顶直接标出实际人数。\n\n'
    for start in [1,51,101]:
        end = start+49
        text += f'''<details>
<summary>展开查看传统榜 #{start}–{end}</summary>

![传统榜第 {start}–{end} 名](charts/traditional/hardest_detail_{start}_{end}.png)

</details>

'''
    text += f'''## 数据与验证

- 150 个关卡全部满足 `rated=true`，`rated_position` 完整覆盖 1–150；第 75 名为 **{levels[74]['name']}**，第 150 名为 **{levels[149]['name']}**。
- 采集到 {summary['approved_record_rows']:,} 条已批准的 100% 记录；将记录中的玩家 ID 与验证者 ID 合并，同一人只计一次。
- 抓取前后核对 150 关的传统排名、关卡 ID 与 verifier 身份，均保持一致。
- 记录接口的 `demon_position__lt` 是综合名次范围，所以扩大到能覆盖传统第 150 名，再按这 150 个已评级关卡 ID 过滤；未评级关卡记录不会进入统计。
- `approved_records_only` 字段保留为对照数据，本页图表统一使用 `including_verifiers` 系列。
- 只覆盖公开批准记录和验证者，不包含未提交的实际通关；数据是在采集区间内取得，并非数据库原子快照。
- 来源：[Pointercrate 传统 Demonlist](https://pointercrate.com/demonlist/)。

## 下载

[传统榜总览 PNG](charts/traditional/hardest_top150_charts.png) · [SVG](charts/traditional/hardest_top150_charts.svg) · [PDF](charts/traditional/hardest_top150_charts.pdf)

[150 个名次统计](hardest_by_rank.csv) · [玩家明细](players.csv) · [高峰明细](peak_levels.csv) · [零值核对](zero_bin_audit.csv) · [统计汇总](summary.json)

[关卡 API 快照](data/levels.json) · [原始批准记录 gzip JSON](data/records.json.gz) · [采集元数据](data/collection.json)

## 复现

安装 Python 的 `matplotlib` 和 `numpy`。使用仓库内的固定快照重算并绘图：

```bash
python scripts/collect_traditional.py --reuse-data
python scripts/render_charts.py
python scripts/update_readme.py
```

如需从 API 抓取新的传统榜快照，将第一条命令改为 `python scripts/collect_traditional.py`，其余步骤相同。
历史版本中的综合榜数据不作为本页传统榜统计结果。
'''
    (ROOT/'README.md').write_text(text, encoding='utf-8')
    print(f'Updated traditional-list report for {total:,} players')


if __name__ == '__main__':
    main()
