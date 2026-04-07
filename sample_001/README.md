## サンプル内容
データの読み込みとプロットのシンプルなプログラム。
### single_plot()
- CSVファイルを読み込む
- x-yデータをプロットする
- 画像として保存する

xとyのデータを持つCSVファイルを data/sample_data_001.csv として用意しています。  
実行後、`output/plot_sample_001.png`のファイルが生成されます。

### multi_plot()
- 複数のプロットを作成する

tとx1~x4のデータを持つCSVファイルを data/sample_data_002.csv として用意しています。  
実行後、`output/plot_sample_002.png`のファイルが生成されます。

## ディレクトリ構成
```
sample_001/
├── main.py
│
├── data/           
│   ├── raw/        ← 生データ
│   └── processed/  ← 編集したデータ
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築
uvを使用します。uvの導入までは事前に行ってください。   
以下のコマンドをターミナルで実行してください。
```
uv init sample_001
cd sample_001

mkdir -p data/raw
mkdir data/processed
mkdir output

uv add pandas matplotlib
```
必要なデータを`data/`に入れてください。

## 実行方法
```
sample_001 % uv run main.py
```
