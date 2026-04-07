import pandas as pd
import matplotlib.pyplot as plt


# 図の設定 (浪川が論文用の図を作るときによく使う設定。フォントサイズは適宜変更。)
plt.rcParams['font.family'] = 'Times New Roman'  # フォントの設定
plt.rcParams['font.size'] = 12  # フォントサイズの設定
plt.rcParams['xtick.direction'] = 'in'  # x軸の目盛りの方向の設定
plt.rcParams['ytick.direction'] = 'in'  # y軸の目盛りの方向の設定


def single_plot():
    """
    データの読み込みと1つのプロットを作成する関数（最小限のコード例）
    """
    # データの読み込み
    data_path = "data/raw/sample_data_001.csv"
    df = pd.read_csv(data_path)

    # データのプロット
    plt.plot(df['x'], df['y']) #　プロットするデータの指定
    plt.title('Title of the Plot') # タイトルの設定
    plt.xlabel('x axis') # x軸ラベルの設定
    plt.ylabel('y axis') # y軸ラベルの設定
    plt.xlim(0, 10)  # x軸の範囲の設定
    plt.ylim(-2, 2)  # y軸の範囲の設定
    plt.savefig("output/plot_sample_001.png", dpi=200)  # 図の保存（dpiは解像度）

def multi_plot():
    """
    複数のプロットを作成する関数（例）
    """
    # データの読み込み
    data_path = "data/raw/sample_data_002.csv"
    df = pd.read_csv(data_path)

    # 図の作成
    fig, axs = plt.subplots(2, 2, figsize=(10, 8))  # 2x2のサブプロットを作成

    # 各サブプロットにデータをプロット
    axs[0, 0].plot(df['t'], df['x1'])
    axs[0, 0].set_title('Plot 1')
    axs[0, 0].set_xlabel('Time (t)')
    axs[0, 0].set_ylabel('x1')
    axs[0, 0].set_xlim(0, 10)
    axs[0, 0].set_ylim(-2, 2)
    
    axs[0, 1].plot(df['t'], df['x2'])
    axs[0, 1].set_title('Plot 2')
    axs[0, 1].set_xlabel('Time (t)')
    axs[0, 1].set_ylabel('x2')
    axs[0, 1].set_xlim(0, 10)
    axs[0, 1].set_ylim(-2, 2)
    
    axs[1, 0].plot(df['t'], df['x3'])
    axs[1, 0].set_title('Plot 3')
    axs[1, 0].set_xlabel('Time (t)')
    axs[1, 0].set_ylabel('x3')
    axs[1, 0].set_xlim(0, 10)
    axs[1, 0].set_ylim(-2, 2)
    
    axs[1, 1].plot(df['t'], df['x4'])
    axs[1, 1].set_title('Plot 4')
    axs[1, 1].set_xlabel('Time (t)')
    axs[1, 1].set_ylabel('x4')
    axs[1, 1].set_xlim(0, 10)
    axs[1, 1].set_ylim(-2, 2)
    
    plt.tight_layout() # レイアウトの調整
    plt.savefig("output/plot_sample_002.png", dpi=200)

if __name__ == "__main__":
    single_plot()
    multi_plot()
