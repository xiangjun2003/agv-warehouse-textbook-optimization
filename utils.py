import csv
import matplotlib.pyplot as plt
import random


# calculate pallets and workstations distance
def getdist(nx, ny):
    dist = abs(nx[0] - ny[0]) + abs(nx[1] - ny[1])
    return dist


def read_map_ws():
    nodes = []
    workstations = []
    nrows = ncols = 0
    with open('./data/map.csv', newline='', encoding='gbk') as csvfile:
        sr = csv.reader(csvfile, delimiter=',')
        for line in sr:
            if line[0].startswith('*'):
                ncols = int(line[1])
                nrows = int(line[2])
            elif not line[0].startswith('#'):
                nodes.append((line[0], int(line[1]), int(line[2])))
                # type of or station is '5'
                if line[0] == '5':
                    workstations.append((int(line[1]), int(line[2])))
    print(f"load warehouse map of size {ncols} X {nrows}")
    return nodes, ncols, nrows, workstations


def read_pallets(cal_sku=False):
    pallets = []
    with open('./data/pallets.csv', newline='', encoding='gbk') as csvfile:
        sr = csv.reader(csvfile, delimiter=',')
        for line in sr:
            if not line[0].startswith('#'):
                if cal_sku:
                    sku = eval('{' + line[0] + '}')
                    quantity = sum(sku.values())
                    pallets.append((int(line[1]), int(line[2]), quantity))
                else:
                    pallets.append((int(line[1]), int(line[2])))
        print(f"choose {len(pallets)} pallets randomly")
    return pallets


def read_agvs(ncols, nrows):
    agvs = []
    with open('./data/bots.csv', newline='', encoding='utf-8-sig') as csvfile:
        sr = csv.reader(csvfile, delimiter=',')
        for line in sr:
            if len(line) >= 5 and not line[0].startswith('#'):
                if random.random() < 0.6:
                    x = int(line[2])
                    y = int(line[3])

                    if 0 <= x < ncols and 0 <= y < nrows:
                        agvs.append((x, y))

    print(f"choose {len(agvs)} AGVs randomly")
    return agvs


def plot_init(nodes, ncols, nrows):
    fig, ax = plt.subplots(1, 1, figsize=(15, 10))
    ax.grid()
    ax.set_xticks(range(ncols + 1))
    ax.set_yticks(range(nrows + 1))
    ax.tick_params(labelleft=False, labelbottom=False)

    color_schema = {'1': 'grey', '2': 'green', '3': 'yellow', '4': 'black', '5': 'blue', '6': 'pink', '7': 'red', '8': 'cyan'}
    for cell in nodes:
        clr = color_schema.get(cell[0], 'blue')
        ax.add_patch(plt.Rectangle((cell[1], cell[2]), 1, 1, color=clr))
    return fig, ax, color_schema


def plot_warehouse(nodes, ncols, nrows):
    fig, ax, _ = plot_init(nodes, ncols, nrows)
    fig.show()


def plot_agv(agvs, pallets, workstations, nodes, ncols, nrows, X, Y):
    fig, ax, _ = plot_init(nodes, ncols, nrows)
    ax.set_xlim(0, ncols)
    ax.set_ylim(0, nrows)

    # create useful parameters
    I = list(range(len(agvs)))
    J = list(range(len(pallets)))

    for i in I:
        ax.add_patch(plt.Circle((agvs[i][0] + 0.5, agvs[i][1] + 0.5), 0.3, color='darkred'))
    for j in J:
        ax.add_patch(plt.Rectangle((pallets[j][0] + 0.2, pallets[j][1] + 0.2), 0.6, 0.6, color='darkgreen'))

    for i in I:
        part1 = X.select(i, '*')
        for j in range(len(part1)):
            if part1[j].x > 0:
                ax.arrow(agvs[i][0] + 0.5, agvs[i][1] + 0.5, pallets[j][0] - agvs[i][0],
                         pallets[j][1] - agvs[i][1], width=0.01, length_includes_head=True, head_width=0.25, color='darkred')

    for j in J:
        part2 = Y.select(j, '*')
        for k in range(len(part2)):
            if part2[k].x > 0:
                ax.arrow(pallets[j][0] + 0.5, pallets[j][1] + 0.5, workstations[k][0] - pallets[j][0],
                         workstations[k][1] - pallets[j][1], width=0.01, length_includes_head=True, head_width=0.25, color='yellow')

    plt.show()


def plot_partition(pallets, workstations, nodes, ncols, nrows, Z, save_path=None):
    fig, ax, color_schema = plot_init(nodes, ncols, nrows)
    ax.set_xlim(0, ncols)
    ax.set_ylim(0, nrows)

    for cell in nodes:
        ax.add_patch(plt.Rectangle((cell[1], cell[2]), 1, 1, color='grey'))

    # create useful parameters
    J = list(range(len(pallets)))
    K = list(range(len(workstations)))

    for k in K:
        clr = color_schema.get(str(int(k / 3) + 2))
        ax.add_patch(plt.Rectangle((workstations[k][0], workstations[k][1]), 1, 1, color=clr))

    for j in J:
        # 【关键修改】：Gurobi 获取变量值必须使用大写的 .X
        vals = [var.X for var in Z.select(j, '*')]
        maxone = max(enumerate(vals), key=lambda x: x[1])
        clr = color_schema.get(str(int(maxone[0] / 3) + 2))
        ax.add_patch(plt.Rectangle((pallets[j][0], pallets[j][1]), 1, 1, color=clr))

    # 【新增功能】：保存图片
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Partition layout successfully saved to {save_path}")

    plt.show()

def plot_layout(pallets, nodes, ncols, nrows, w):
    fig, ax, _ = plot_init(nodes, ncols, nrows)

    N = list(range(len(pallets)))

    for j in N:
        ax.add_patch(plt.Rectangle((pallets[j][0] + 0.1, pallets[j][1] + 0.1), 0.8, 0.8, color='darkgreen'))
        if w[j].x > 0:
            ax.add_patch(plt.Rectangle((pallets[j][0] + 0.2, pallets[j][1] + 0.2), 0.6, 0.6, color='darkred'))

    plt.show()

def plot_warehouse(nodes, ncols, nrows, save_path=None):
    fig, ax, _ = plot_init(nodes, ncols, nrows)
    
    # 如果传入了保存路径，则将图片保存到本地
    if save_path:
        # dpi=300 保证图片的高清画质，bbox_inches='tight' 可以自动裁剪掉周围多余的白边
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Initial warehouse layout successfully saved to {save_path}")
        
    plt.show()


if __name__ == '__main__':
    random.seed(0)
    nodes, ncols, nrows, _ = read_map_ws()
    
    # 在这里加入 save_path 参数
    plot_warehouse(nodes, ncols, nrows, save_path='initial_warehouse_layout.png')
    
    pallets = read_pallets()
    agvs = read_agvs(ncols, nrows)
