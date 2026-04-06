import pandas as pd
import matplotlib.pyplot as plt


# 図の設定 (浪川が論文用の図を作るときによく使う設定。フォントサイズは適宜変更。)
plt.rcParams['font.family'] = 'Times New Roman'  # フォントの設定
plt.rcParams['font.size'] = 12  # フォントサイズの設定
plt.rcParams['xtick.direction'] = 'in'  # x軸の目盛りの方向の設定
plt.rcParams['ytick.direction'] = 'in'  # y軸の目盛りの方向の設定


def main():
    """
    データの読み込みとプロットの関数（最小限のコード例）
    """
    # データの読み込み
    data_path = "data/raw/sample_data.csv"
    df = pd.read_csv(data_path)

    # データのプロット
    plt.plot(df['x'], df['y']) #　プロットするデータの指定
    plt.title('Title of the Plot') # タイトルの設定
    plt.xlabel('x axis') # x軸ラベルの設定
    plt.ylabel('y axis') # y軸ラベルの設定
    plt.xlim(0, 10)  # x軸の範囲の設定
    plt.ylim(-2, 2)  # y軸の範囲の設定
    plt.savefig("output/plot_sample.png", dpi=200)  # 図の保存（dpiは解像度）

if __name__ == "__main__":
    main()
