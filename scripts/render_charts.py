"""Re-render the published player-count snapshot without fetching new records."""
import csv
import json
import os
import statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'charts' / 'traditional'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/pointercrate-chart-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/pointercrate-chart-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
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
    assert summary['list_type'] == 'traditional_demonlist' and summary['rank_field'] == 'rated_position'
    levels = json.loads((ROOT / 'data' / 'levels.json').read_text())
    assert all(d['rated'] for d in levels)
    assert [d['rated_position'] for d in levels] == list(range(1,151))
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
    return rows, summary, peaks


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
    ax.set_xlabel('传统 Demonlist 名次 N（越小越难）', labelpad=7)
    ax.tick_params(axis='both', length=0, pad=6)
    # Main / Extended List boundary.
    ax.axvline(75.5, color='#526279', lw=1.75, ls=(0, (9, 5)), zorder=2)


def add_list_labels(ax):
    ax.text(.25, 1.035, 'Main List  ·  #1–75', transform=ax.transAxes, ha='center', fontsize=10.5, color=INK)
    ax.text(.75, 1.035, 'Extended List  ·  #76–150', transform=ax.transAxes, ha='center', fontsize=10.5, color=INK)


def draw_distribution(ax, rows, peaks, upper=None):
    style_axis(ax)
    peak_ranks = {r['rank'] for r in peaks}
    x = np.array([r['rank'] for r in rows])
    y = np.array([r[COUNT_FIELD] for r in rows])
    ax.set_yscale('function', functions=(np.sqrt, np.square))
    ax.bar(x, y, width=.8, color=[ORANGE if n in peak_ranks else BLUE for n in x], zorder=3)
    # Explicit dots distinguish zero-count bins from missing data.
    ax.scatter(x[y == 0], np.zeros(sum(y == 0)), s=7, c='#94a3b8', zorder=4, clip_on=False)
    upper = upper or max(355, int(np.ceil(max(y)*1.15/50)*50))
    ticks = [0, 1, 5, 10, 25, 50, 100, 200, 300] + list(range(400, upper, 100))
    ax.set_ylim(0, upper)
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


def draw_peak_table(ax, peaks):
    ax.set_axis_off()
    ax.text(0, 1, '高峰关卡', fontsize=15, fontweight='bold', va='top')
    ax.text(0, .96, '名次 / 关名 / Hardest 人数（含 verifier）', fontsize=8.5, color='#64748b', va='top')
    start, step = .91, min(.0275, .55/max(1,len(peaks)))
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
    note += '\n零值：无人以该关为 Hardest，\n并非该关无人通关或没有 verifier。'
    ax.text(0, bottom-.19, note, fontsize=8.5, color='#64748b', va='top', linespacing=1.7)


def render(rows, summary, peaks):
    setup_fonts()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    total = summary['unique_players_including_verifiers']
    stamp = datetime.fromisoformat(summary['finished_at_utc']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
    upper = max(355, int(np.ceil(max(r[COUNT_FIELD] for r in rows)*1.15/50)*50))
    fig = plt.figure(figsize=(21, 12), facecolor=BG)
    grid = fig.add_gridspec(2, 2, width_ratios=[4.7, 1.6], height_ratios=[1.15, 1], left=.055, right=.98, top=.80, bottom=.10, hspace=.43, wspace=.10)
    distribution = fig.add_subplot(grid[0, 0])
    cumulative = fig.add_subplot(grid[1, 0])
    table = fig.add_subplot(grid[:, 1])
    draw_distribution(distribution, rows, peaks, upper)
    draw_cumulative(cumulative, rows)
    distribution.set_title('01  Hardest 恰好为第 N 名的人数（含 verifier）', loc='left', fontsize=14, pad=32)
    cumulative.set_title('02  Hardest 位于前 N 名的累计人数（含 verifier）', loc='left', fontsize=14, pad=32)
    add_list_labels(distribution)
    add_list_labels(cumulative)
    draw_peak_table(table, peaks)
    fig.text(.055, .96, '传统 Demonlist Top 150 · 玩家 Hardest 分布', fontsize=25, fontweight='bold', va='top')
    fig.text(.055, .905, f"统一口径：{summary['unique_players_including_verifiers']:,} 人（含 verifier），按玩家 ID 去重；累计图由分布图逐柱累加得到", fontsize=12, color='#475569')
    fig.text(.055, .875, '平方根纵轴保留高峰，同时让 1–25 人的小柱更易辨认；橙色标出明显高于周边的关卡。', fontsize=10.5, color='#64748b')
    footer = f'传统榜单：150 关均已评级  |  数据快照：{stamp} 北京时间  |  按玩家 ID 去重，包含 verifier'
    footer += '\n0 表示无人以该关为 Hardest；verifier 若有更难通关，则归入更高名次。'
    fig.text(.055, .025, footer, fontsize=9.2, color='#64748b', linespacing=1.6)
    fig.savefig(OUTPUT / 'hardest_top150_charts.png', dpi=160)
    fig.savefig(OUTPUT / 'hardest_top150_charts.svg')
    svg = OUTPUT / 'hardest_top150_charts.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n', encoding='utf-8')
    fig.savefig(OUTPUT / 'hardest_top150_charts.pdf')
    plt.close(fig)
    # Individual wide charts keep text legible in GitHub's README display.
    for name, draw, title, sub in [
        ('hardest_distribution', lambda ax: draw_distribution(ax, rows, peaks, upper), '传统榜 · Hardest 恰好为第 N 名的人数（含 verifier）', f'统一口径：{total:,} 人，150 关均已评级 · 平方根纵轴，刻度为实际人数 · 橙柱关名及人数见高峰明细。'),
        ('hardest_cumulative', lambda ax: draw_cumulative(ax, rows), '传统榜 · Hardest 位于前 N 名的累计人数（含 verifier）', f'统一口径：{total:,} 人，150 关均已评级 · 由分布图从第 1 名逐柱累加 · 线性纵轴。'),
    ]:
        f, ax = plt.subplots(figsize=(17, 6.4), facecolor=BG)
        f.subplots_adjust(left=.06, right=.985, top=.78, bottom=.18)
        draw(ax)
        add_list_labels(ax)
        f.suptitle(title, x=.06, ha='left', fontsize=21, y=.975)
        f.text(.06, .86, sub, fontsize=10, color='#64748b')
        footer = f'{stamp} 北京时间快照 · 传统 Demonlist · 含 verifier · 大虚线：主榜 / 扩展榜分界'
        footer += '\n0 表示无人以该关为 Hardest；verifier 若有更难通关，则归入更高名次。'
        f.text(.06,.02,footer,fontsize=9,color='#64748b',linespacing=1.5)
        f.savefig(OUTPUT/f'{name}.png', dpi=160)
        plt.close(f)
    # Separate detailed panels improve legibility in GitHub's narrower README column.
    for start in [1, 51, 101]:
        subset = rows[start-1:start+49]
        f, ax = plt.subplots(figsize=(15, 5), facecolor=BG)
        f.subplots_adjust(left=.065, right=.985, top=.78, bottom=.18)
        draw_distribution(ax, subset, [], upper)
        ax.set_xlim(start-.65, start+49.65)
        ax.set_xticks([r['rank'] for r in subset])
        ax.tick_params(axis='x', labelsize=8, rotation=90)
        for r in subset:
            value = r['hardest_players_including_verifiers']
            ax.annotate(str(value), (r['rank'], value), xytext=(0, 5), textcoords='offset points', ha='center', fontsize=8, color=INK)
        f.suptitle(f"传统榜精细视图 · #{start}–#{start+49}（含 verifier）", x=.065, ha='left', fontsize=17, y=.96)
        f.text(.065,.86,f'统一口径：{total:,} 人，150 关均已评级 · 平方根纵轴 · 柱上为实际人数，每位玩家只归入其最难通关名次',fontsize=10,color='#64748b')
        f.savefig(OUTPUT/f'hardest_detail_{start}_{start+49}.png',dpi=160)
        plt.close(f)
    print(f'Rendered charts; {len(peaks)} peak levels; {summary["unique_players_including_verifiers"]:,} players including verifiers')


if __name__ == '__main__':
    render(*load_data())
