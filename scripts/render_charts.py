"""Re-render the published snapshot without fetching new completion records.

Optional GDDL enrichment: gddl_tiers.csv with rank, tier, rating, level_id,
and source_url columns, plus gddl_metadata.json with collection provenance.
"""
import csv
import json
import os
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', '/tmp/pointercrate-chart-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/pointercrate-chart-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

COUNT_FIELD = 'hardest_players_including_verifiers'
CUMULATIVE_FIELD = 'cumulative_including_verifiers'


def load_data():
    with (ROOT / 'hardest_by_rank.csv').open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in row:
            if key != 'level_name':
                row[key] = int(row[key])
    assert [r['rank'] for r in rows] == list(range(1, 151))
    summary = json.loads((ROOT / 'summary.json').read_text())
    counts = np.array([r[COUNT_FIELD] for r in rows], dtype=int)
    cumulative = np.array([r[CUMULATIVE_FIELD] for r in rows], dtype=int)
    assert np.array_equal(np.cumsum(counts), cumulative), 'Every cumulative bin must equal the sum of the verifier-inclusive histogram bins'
    assert counts.sum() == summary['unique_players_including_verifiers']
    assert cumulative[-1] == summary['unique_players_including_verifiers']
    peaks = []
    for i, r in enumerate(rows):
        neighbors = [t['hardest_players_including_verifiers'] for j, t in enumerate(rows) if 0 < abs(i - j) <= 4]
        median = statistics.median(neighbors)
        count = r['hardest_players_including_verifiers']
        if count >= 35 and count >= 3 * max(1, median):
            peaks.append({**r, 'neighbor_median': median, 'ratio_to_neighbor_median': round(count / max(1, median), 2)})
    with (ROOT / 'peak_levels.csv').open('w', encoding='utf-8-sig', newline='') as f:
        keys = ['rank', 'level_name', 'hardest_players_including_verifiers', 'neighbor_median', 'ratio_to_neighbor_median']
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        w.writerows(peaks)
    tiers = {}
    if (ROOT / 'gddl_tiers.csv').exists():
        with (ROOT / 'gddl_tiers.csv').open(encoding='utf-8-sig') as f:
            tiers = {int(r['rank']): int(r['tier']) if r['tier'] else None for r in csv.DictReader(f)}
        assert set(tiers) == set(range(1, 151))
    return rows, summary, peaks, tiers


BLUE, ORANGE, TEAL, INK = '#2563eb', '#dc6b25', '#0d9488', '#17253b'
BG, GRID = '#f8fafc', '#e0e6ee'


def setup_fonts():
    font_path = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    family = FontProperties(fname=font_path).get_name() if font_path.exists() else 'DejaVu Sans'
    plt.rcParams.update({'font.family': family, 'axes.unicode_minus': False, 'font.size': 10, 'text.color': INK, 'axes.labelcolor': INK, 'xtick.color': '#526279', 'ytick.color': '#526279', 'savefig.facecolor': BG})


def style_axis(ax):
    ax.set_facecolor(BG)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_color('#bdc9d8')
    ax.set_axisbelow(True)
    ax.grid(axis='y', color=GRID, lw=.7)
    ax.set_xlim(.2, 150.8)
    ax.set_xticks([1] + list(range(10, 151, 10)))
    ax.set_xlabel('Pointercrate 名次 N（越小越难）', labelpad=7)
    ax.tick_params(axis='both', length=0, pad=6)
    # Actual list boundary; unrelated to GDDL tiers.
    ax.axvline(75.5, color='#526279', lw=1.75, ls=(0, (9, 5)), zorder=2)


def resolve_plot_tiers(tiers, rows):
    """For missing tiers, inherit the next ranked level's plotting tier.

    Keep official/source data unchanged. Consecutive missing values inherit
    recursively, working backwards from #150.
    """
    if not tiers:
        return {}
    filled, sources = {}, {}
    next_tier, next_rank = None, None
    for rank in range(150, 0, -1):
        if tiers[rank] is not None:
            next_tier, next_rank = tiers[rank], rank
        if next_tier is None:
            raise ValueError(f'Cannot inherit a tier below #{rank}: no lower-ranked source is available')
        filled[rank], sources[rank] = next_tier, next_rank
    with (ROOT/'gddl_plot_tiers.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['rank', 'level_name', 'source_gddl_tier', 'plot_tier', 'inherited_from_lower_rank', 'tier_source_rank'])
        for row in rows:
            n = row['rank']
            w.writerow([n, row['level_name'], tiers[n] if tiers[n] is not None else '', filled[n], tiers[n] is None, sources[n]])
    return filled


def tier_runs(tiers):
    runs = []
    for rank in range(1, 151):
        tier = tiers[rank]
        if not runs or runs[-1][2] != tier:
            runs.append([rank, rank, tier])
        else:
            runs[-1][1] = rank
    return runs


def add_tier_dividers(ax, tiers):
    """Small dashes mark every actual change in the resolved plotting tiers."""
    ax.text(.25, 1.225, 'Main List  ·  #1–75', transform=ax.transAxes, ha='center', fontsize=11, color=INK)
    ax.text(.75, 1.225, 'Extended List  ·  #76–150', transform=ax.transAxes, ha='center', fontsize=11, color=INK)
    if not tiers:
        return
    runs = tier_runs(tiers)
    for a, b in zip(runs, runs[1:]):
        boundary = a[1]+.5
        # The heavier main/extended line takes precedence if boundaries coincide.
        if boundary != 75.5:
            ax.axvline(boundary, color='#9aa8b7', lw=.7, ls=(0, (2, 3)), alpha=.75, zorder=1.5)
    for start, end, tier in runs:
        width = end-start+1
        ax.text((start+end)/2, 1.025, f'T{tier}', transform=ax.get_xaxis_transform(), ha='center', va='bottom', rotation=0 if width>=4 else 90, fontsize=9 if width>=4 else 6.7, color='#526279', clip_on=False)


def add_tier_strip(ax, tiers):
    if not tiers:
        ax.text(.01, 1.08, '主榜 1–75', transform=ax.transAxes, fontsize=9, color='#64748b')
        ax.text(.51, 1.08, '扩展榜 76–150', transform=ax.transAxes, fontsize=9, color='#64748b')
        return
    values = sorted({t for t in tiers.values() if t is not None}, reverse=True)
    # Fixed scale: T34 soft green -> T39 soft red. Preserve the mapping if a
    # future dataset has fewer tiers, rather than renormalizing observed values.
    cmap = LinearSegmentedColormap.from_list('gddl_soft_green_to_red', ['#6fa88c', '#bcc39b', '#d9b497', '#c47772'])
    color = {t: cmap(float(np.clip((t-34)/5, 0, 1))) for t in values}
    for rank, tier in tiers.items():
        ax.axvspan(rank - .5, rank + .5, ymin=1.02, ymax=1.10, facecolor=color.get(tier, '#cbd5e1'), clip_on=False)
    ax.text(0, 1.205, 'GDDL tier（缺失沿用下一名，仅绘图）', transform=ax.transAxes, fontsize=8.5, color='#64748b')
    legend_step = .61 / max(len(values), 1)
    for i, tier in enumerate(values):
        loc = .37 + i*legend_step
        ax.plot([loc], [1.225], marker='s', markersize=6, color=color[tier], transform=ax.transAxes, clip_on=False)
        ax.text(loc+.01, 1.205, f'T{tier}', fontsize=8.5, transform=ax.transAxes, color=INK)
    runs = tier_runs(tiers)
    for start, end, tier in runs:
        if end - start + 1 >= 7 and tier is not None:
            ax.text((start+end)/2, 1.125, f'T{tier}', transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=9, color=INK, clip_on=False)


def draw_distribution(ax, rows, peaks):
    style_axis(ax)
    peak_ranks = {r['rank'] for r in peaks}
    x = np.array([r['rank'] for r in rows])
    y = np.array([r[COUNT_FIELD] for r in rows])
    ax.set_yscale('function', functions=(np.sqrt, np.square))
    ax.bar(x, y, width=.8, color=[ORANGE if n in peak_ranks else BLUE for n in x], zorder=3)
    # Explicit dots distinguish zero-count bins from missing data.
    ax.scatter(x[y == 0], np.zeros(sum(y == 0)), s=7, c='#94a3b8', zorder=4, clip_on=False)
    ticks = [0, 1, 5, 10, 25, 50, 100, 200, 300]
    ax.set_ylim(0, 355)
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_ylabel('人数（平方根刻度）', labelpad=10)


def draw_cumulative(ax, rows):
    style_axis(ax)
    # Both charts derive from exactly the same verifier-inclusive rank-bin series.
    cumulative = np.cumsum([r[COUNT_FIELD] for r in rows])
    ax.bar([r['rank'] for r in rows], cumulative, color=TEAL, width=.8, zorder=3)
    total = int(cumulative[-1])
    ax.set_ylim(0, total * 1.24)
    ax.set_ylabel('累计去重人数（线性刻度）', labelpad=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:,.0f}'))
    for n in [10, 30, 50, 75, 100, 125, 150]:
        y = int(cumulative[n-1])
        ax.annotate(f'Top {n}\n{y:,} · {y/total:.1%}', xy=(n,y), xytext=(-3 if n==150 else 0, 9), textcoords='offset points', ha='right' if n==150 else 'center', fontsize=8.5, color='#0f766e')


def draw_peak_table(ax, peaks, tiers):
    ax.set_axis_off()
    ax.text(0, 1, '高峰关卡', fontsize=15, fontweight='bold', va='top')
    ax.text(0, .96, '名次 / 关名 / Hardest 人数（含 verifier）', fontsize=8.5, color='#64748b', va='top')
    start, step = .91, .0275
    for i, r in enumerate(peaks):
        y = start-i*step
        ax.text(0, y, f"#{r['rank']:>3}", fontsize=9.2, color=ORANGE, va='center')
        ax.text(.17, y, r['level_name'], fontsize=9.2, va='center')
        ax.text(.99, y, str(r['hardest_players_including_verifiers']), fontsize=9.4, ha='right', va='center', fontweight='bold')
        ax.axhline(y - .019, xmin=0, xmax=1, lw=.5, color='#e2e8f0')
    bottom = start - len(peaks)*step - .005
    ax.text(0, bottom, '高峰筛选：人数 ≥35，且至少为\n前后各 4 名中位数的 3 倍。\n标注反映人数集中，不代表难度异常。', fontsize=8.5, color='#64748b', va='top', linespacing=1.7)
    ax.text(0, bottom-.15, '读图提示', fontsize=11, fontweight='bold', va='top')
    note = '两图统一包含 verifier，均按玩家 ID 去重。\n上图：最难通关恰好为该名次。\n下图：上图从第 1 名逐柱累加。\n大虚线：主榜 / 扩展榜分界。'
    if tiers:
        note += '\n上图小虚线：tier 变化；下图保留色带。\n未评级关卡沿用下一名 tier（仅绘图）。'
    note += '\n零值：无人以该关为 Hardest，\n并非该关无人通关或没有 verifier。'
    ax.text(0, bottom-.19, note, fontsize=8.5, color='#64748b', va='top', linespacing=1.7)


def render(rows, summary, peaks, tiers):
    setup_fonts()
    plot_tiers = resolve_plot_tiers(tiers, rows)
    fig = plt.figure(figsize=(21, 12), facecolor=BG)
    grid = fig.add_gridspec(2, 2, width_ratios=[4.7, 1.6], height_ratios=[1.15, 1], left=.055, right=.98, top=.755, bottom=.10, hspace=.62, wspace=.10)
    distribution = fig.add_subplot(grid[0, 0])
    cumulative = fig.add_subplot(grid[1, 0])
    table = fig.add_subplot(grid[:, 1])
    draw_distribution(distribution, rows, peaks)
    draw_cumulative(cumulative, rows)
    # Leave title/annotation spacing independent of the color strip.
    distribution.set_title('01  Hardest 恰好为第 N 名的人数（含 verifier）', loc='left', fontsize=14, pad=66)
    cumulative.set_title('02  Hardest 位于前 N 名的累计人数（含 verifier）', loc='left', fontsize=14, pad=66)
    add_tier_dividers(distribution, plot_tiers)
    add_tier_strip(cumulative, plot_tiers)
    draw_peak_table(table, peaks, tiers)
    fig.text(.055, .96, 'Pointercrate Top 150 · 玩家 Hardest 分布', fontsize=25, fontweight='bold', va='top')
    fig.text(.055, .905, f"统一口径：{summary['unique_players_including_verifiers']:,} 人（含 verifier），按玩家 ID 去重；累计图由分布图逐柱累加得到", fontsize=12, color='#475569')
    fig.text(.055, .875, '平方根纵轴保留高峰，同时让 1–25 人的小柱更易辨认；橙色标出明显高于周边的关卡。', fontsize=10.5, color='#64748b')
    footer = '通关数据快照：2026-10-24 11:35 北京时间  |  按玩家 ID 去重  |  仅公开批准的 100% 记录与榜单验证者'
    if tiers:
        metadata = json.loads((ROOT/'gddl_metadata.json').read_text())
        footer += '\nGDDL 缺失评级仅在绘图时沿用下一名 tier；源数据空值保留。0 表示无人以该关为 Hardest。'
    else:
        footer += '\nGDDL 评级尚未取得：本图未绘制 GDDL tier 分区，也未将名次推算成 tier。'
    fig.text(.055, .025, footer, fontsize=9.2, color='#64748b', linespacing=1.6)
    fig.savefig(ROOT / 'hardest_top150_charts.png', dpi=160)
    fig.savefig(ROOT / 'hardest_top150_charts.svg')
    svg = ROOT / 'hardest_top150_charts.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n', encoding='utf-8')
    fig.savefig(ROOT / 'hardest_top150_charts.pdf')
    plt.close(fig)
    # Individual wide charts keep text legible in GitHub's README display.
    for name, draw, title, sub in [
        ('hardest_distribution', lambda ax: draw_distribution(ax, rows, peaks), 'Hardest 恰好为第 N 名的人数（含 verifier）', '统一口径：2,952 人，按玩家 ID 去重 · 平方根纵轴，刻度为实际人数 · 橙柱的关名及人数见高峰明细。'),
        ('hardest_cumulative', lambda ax: draw_cumulative(ax, rows), 'Hardest 位于前 N 名的累计人数（含 verifier）', '统一口径：2,952 人，按玩家 ID 去重 · 由分布图从第 1 名逐柱累加 · 线性纵轴。'),
    ]:
        f, ax = plt.subplots(figsize=(17, 6.4), facecolor=BG)
        f.subplots_adjust(left=.06, right=.985, top=.70, bottom=.18)
        draw(ax)
        if name == 'hardest_distribution':
            add_tier_dividers(ax, plot_tiers)
        else:
            add_tier_strip(ax, plot_tiers)
        f.suptitle(title, x=.06, ha='left', fontsize=21, y=.975)
        f.text(.06, .86, sub, fontsize=10, color='#64748b')
        footer = '2026-10-24 11:35 北京时间快照 · 含 verifier · 大虚线：主榜 / 扩展榜分界'
        if name == 'hardest_distribution':
            footer += '\n小虚线：tier 变化，未评级沿用下一名 tier；0 表示无人以该关为 Hardest，verifier 若有更难通关则计入更高名次。'
        else:
            footer += '\nGDDL 色带：未评级沿用下一名 tier，仅用于绘图。'
        f.text(.06,.02,footer,fontsize=9,color='#64748b',linespacing=1.5)
        f.savefig(ROOT/f'{name}.png', dpi=160)
        plt.close(f)
    # Separate detailed panels improve legibility in GitHub's narrower README column.
    for start in [1, 51, 101]:
        subset = rows[start-1:start+49]
        f, ax = plt.subplots(figsize=(15, 5), facecolor=BG)
        f.subplots_adjust(left=.065, right=.985, top=.78, bottom=.18)
        draw_distribution(ax, subset, [])
        ax.set_xlim(start-.65, start+49.65)
        ax.set_xticks([r['rank'] for r in subset])
        ax.tick_params(axis='x', labelsize=8, rotation=90)
        for r in subset:
            value = r['hardest_players_including_verifiers']
            ax.annotate(str(value), (r['rank'], value), xytext=(0, 5), textcoords='offset points', ha='center', fontsize=8, color=INK)
        f.suptitle(f"逐名次精细视图 · #{start}–#{start+49}（含 verifier）", x=.065, ha='left', fontsize=17, y=.96)
        f.text(.065,.86,'统一口径：2,952 人，按玩家 ID 去重 · 平方根纵轴 · 柱上为实际人数，每位玩家只归入其最难通关名次',fontsize=10,color='#64748b')
        f.savefig(ROOT/f'hardest_detail_{start}_{start+49}.png',dpi=160)
        plt.close(f)
    print(f'Rendered charts; {len(peaks)} peaks; GDDL coverage: {sum(t is not None for t in tiers.values())}/150')


if __name__ == '__main__':
    render(*load_data())
