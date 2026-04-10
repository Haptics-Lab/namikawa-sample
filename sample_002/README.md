## サンプル内容
NIのDAQでCSVにデータを記録するプログラム。

## ディレクトリ構成
```
sample_002/
├── main.py
│
├── src/           
│   └── ni_adc.py   ← 編集したデータ
│
├── output/         ← 結果など
│
└── README.md
```

## 環境構築
OSはWindowsを想定しています。  
uvを使用します。uvの導入までは事前に行ってください。  
また、必要に応じてNI-DAQmx driverをインストールしてください。  

`sample_002/`をPCにコピーして、以下のコマンドを実行してください。
```
sample_002 % uv sync
```
必要なライブラリが用意できていれば、`ni_adc.py`のみでも動きます。

## 実行方法
```
sample_001 % uv run main.py
```